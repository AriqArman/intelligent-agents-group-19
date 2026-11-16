# Bidding — design notes (Ariq)

Notes for the report and the design journal. The code is in [`group19.py`](../../group19.py).

## Design
- **Bid = marginal cost × (1 + margin)**, with margin = 0.4 by default.
- **Marginal cost** is the extra fuel cost of fitting the trade into a vessel's schedule. It covers the ballast leg to the pick-up, the laden leg, loading and unloading, all priced with `vessel.get_cost`. The idle fuel the vessel would have burnt anyway during that time is subtracted. It is computed as cost(schedule with trade) − cost(schedule without).
- **Bid set:** greedy cheapest insertion across the fleet. We bid only on trades that fit together into feasible schedules (`verify_schedule`), so we cannot win a set we are unable to deliver. Trades no vessel can deliver in time get no bid.
- **Bundle protection:** a trade can look cheap only because it shares a route with another trade we might not win. Each bid therefore uses the larger of its cost inside the joint plan and its cost on its own.
- **Scheduling (placeholder):** the same greedy insertion runs in `receive`. Only vessels with no committed work take new trades (see "MABLE quirk" below). If a won trade does not fit, the plan is retried while checking every insertion option. Cost estimation lives in separate methods (`marginal_cost`, `schedule_cost`, `route_cost`), so a teammate's scheduler can reuse or replace it.
- **Speed:** each option is priced and checked against its time windows on a plain task list first, and MABLE's slow `verify_schedule` (~3 ms per call) runs only on the cheapest plausible options. Planning has a 40 s budget against MABLE's 60 s timeout. With 10 ships, `inform` takes 2 s for 30 trades (down from 22 s) and 26 s for 140 trades.

## Why (plain-language)
- In each auction the **lowest bid wins**, but the winner is paid the **second-lowest bid**. Bidding higher than your true cost does not raise your pay when you win, because your pay is set by the next company's bid. It only makes you lose trades you could have done profitably. Bidding below cost risks winning a trade that pays less than it costs. So the textbook answer is to bid your true cost (Vickrey, 1961), and the 1st-place AAMAS'25 team (Mai et al., Delft) built their pricing on the same principle.
- **Why add a margin, then?** Three reasons:
  1. If nobody else bids, MABLE pays you **your own bid** (`shipping_market.py`: a sole bidder is paid its own amount), so the margin is pure profit there.
  2. Our cost ignores opportunity cost: a ship tied up on a cheap trade cannot take a better one next month.
  3. The estimate runs 2–6% low.
- **Ideas taken from Mai et al. (AAMAS'25, 1st place):** minimum-cost insertion for both pre-auction costing and post-auction scheduling, marginal-cost pricing, and the risk of pricing bundles when only part of the bundle is won. Implemented from the ideas, not their code. Not yet used: their multi-start search, absolute/marginal cost blend, and frequency threshold.

## Validation
- **Cost estimator:** across a 12-auction run (15 trades/auction, 4 ships), predicted active fuel per vessel came in 1.6–5.8% below the simulator's (e.g. 5991 predicted against 6148 actual). A single-trade check matched leg times exactly.
- **Stress test:** a solo run with 140 trades/auction × 12 auctions on a mixed fleet (4 Suezmax, 4 Aframax, 2 VLCC). Solo is the worst case for `receive`, because we win every bid. Result: no timeouts, no swallowed exceptions, penalty 0, and 2 min wall time.
- **MABLE quirk (important for the scheduler owner):** when we re-applied schedules to vessels that already had committed work, a few legs were charged absurd amounts of fuel. One Qingdao → March Point leg was logged as a 59.8 h journey and charged 15,214 fuel. Measured normal legs, for comparison: 3,614 nm in ballast cost 746, and 5,083 nm laden cost 2,708.
  - Likely cause: MABLE re-issues the in-progress leg with a shortened duration, so the implied speed is very high and fuel climbs steeply with speed. This is not confirmed.
  - Rule that works: only free vessels (empty schedules) take new trades, and that removed every spike.
  - A better scheduler should test carefully before adding work to busy vessels.

## Results
Setup: 12 monthly auctions against MABLE's `MyArchEnemy` and `TheScheduler`, all with the same fleet of N Suezmax ships. Seed 0 (deterministic). Run `python sweep.py`; the full table is in `runs/sweep.md`. Margin −1 = never bid; this is the idle-fuel floor, i.e. what owning the fleet costs.

| trades/auction, ships | no bids | m=0.0 | m=0.1 | m=0.2 | **m=0.4** | m=1.0 | best rival (at m=0.4) |
|---|---|---|---|---|---|---|---|
| 5, 2  | −5956 | −5013 | −5559 | −5416 | **−4926** | −4580 | −6265 |
| 10, 3 | −9049 | −6532 | −5972 | −6397 | **−4008** | −4538 | −7710 |
| 15, 4 | −11918 | −8284 | −7879 | −8481 | **−7567** | −3715 | −8112 |
| 30, 4 | −12097 | −6421 | −4415 | −3502 | **+322** | +7228 | −17585 |

- Bidding always beats not bidding, so trades make money after their own costs. Penalties are 0 in every run.
- Small markets cannot cover the fixed idle fuel. Income turns positive once there are enough trades (30/auction).
- **m=0.4 beats the best rival in all four settings.** m=1.0 earns more in absolute terms but loses to the rival in 2 of 4 settings. Ranking is relative, so 0.4 is the default for now. This is provisional: it rests on one trade draw per setting (MABLE's seed is fixed at 0), and income is not monotonic in margin.
- **Caveats:**
  - There is one seed per setting, and the rivals are naive (MyArchEnemy prices only the laden leg).
  - Real opponents will undercut, which pushes the best margin down. Re-tune against the preliminary-tournament feedback (27 Nov).
  - Example fleets only; the tournament mixes ship types.
- **Next steps:**
  - Tune the margin per fleet size and market size.
  - Model opponents from `auction_ledger`: their winning bids show how far above cost we can go.
  - Use `pre_inform` (next month's trades) to discount trades that end near future pick-ups.
