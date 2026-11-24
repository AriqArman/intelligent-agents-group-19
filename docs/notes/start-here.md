# Start here: build the agent yourself, step by step

You write a practice agent in a new file, `my_agent.py`. Every step below has been run, and each one shows what you should see. Run it all with:

```
.venv/Scripts/python run_mine.py
```

**Live dashboard (recommended):** run `python tools/live.py` in a second terminal and leave it running. A browser page opens with a Run button, your `print()` output, income, penalty, trades won per month, and a "did my change help?" chart across runs. Tick "Re-run when I save my_agent.py" and it reruns every time you save. Errors, including ones MABLE hides, appear in a red box.

`group19.py` (the finished agent) is not touched. Look at it only when you get stuck.

---

## The whole game in 5 sentences
1. Every month MABLE shows every company a list of **trades**. A trade means carrying this much oil from port A to port B, picking it up and dropping it off within given time windows.
2. Your agent says how much it wants to be **paid** for each trade it wants. This is your **bid**.
3. The **cheapest bid wins** each trade.
4. You must then plan which of your ships does it. If you fail to deliver, you pay a big **penalty**.
5. Your score is the money you're paid minus the fuel your ships burn.

So your agent needs exactly two functions:

| Function | When MABLE calls it | What you give back |
|---|---|---|
| `inform(self, trades)` | a new month's trades appear | a list of `Bid(amount=..., trade=...)` |
| `receive(self, contracts, auction_ledger)` | the auction is over | nothing, but you **must** call `self.apply_schedules(...)` so your ships actually sail |

Useful things you can read inside them:
- `self.fleet`: your ships.
- `vessel.schedule`: what that ship is already doing.
- `self.headquarters.get_network_distance(port_a, port_b)`: the distance between two ports.
- `trade.origin_port`, `trade.destination_port`, `trade.amount`: where the cargo goes and how much.

---

## Step 1: an agent that does nothing
Create `my_agent.py`:

```python
from mable.cargo_bidding import TradingCompany
from mable.transport_operation import Bid


class Company19(TradingCompany):
    def inform(self, trades, *args, **kwargs):
        print(f"month: {len(trades)} trades offered")
        return []                      # no bids

    def receive(self, contracts, auction_ledger=None, *args, **kwargs):
        self.apply_schedules({})       # nothing to plan
```

**Run it. You should see** `month: 5 trades offered` six times.
**Lesson:** this is the loop: trades come in, you bid, you plan, and the next month starts.

---

## Step 2: work out what a trade costs you
Add this method to the class. For each ship it adds up the fuel for four things: sailing empty to the pick-up, loading, sailing full to the drop-off, and unloading. It keeps the cheapest ship.

```python
    def trade_cost(self, trade):
        hq = self.headquarters
        best = None
        for vessel in self.fleet:
            to_pickup = hq.get_network_distance(vessel.location, trade.origin_port)
            laden = hq.get_network_distance(trade.origin_port, trade.destination_port)
            t_empty = vessel.get_travel_time(to_pickup)
            t_full = vessel.get_travel_time(laden)
            t_load = vessel.get_loading_time(trade.cargo_type, trade.amount)
            fuel = (vessel.get_ballast_consumption(t_empty, vessel.speed)
                    + vessel.get_laden_consumption(t_full, vessel.speed)
                    + vessel.get_loading_consumption(t_load)
                    + vessel.get_unloading_consumption(t_load))
            cost = vessel.get_cost(fuel)
            if best is None or cost < best:
                best = cost
        return best
```

Then bid **cost + 40%** on every trade:

```python
    MARGIN = 0.4

    def inform(self, trades, *args, **kwargs):
        bids = [Bid(amount=self.trade_cost(t) * (1 + self.MARGIN), trade=t) for t in trades]
        print(f"month: {len(trades)} offered, bidding on {len(bids)}")
        return bids
```

And in `receive`, give each won trade to the first ship it fits on:

```python
    def receive(self, contracts, auction_ledger=None, *args, **kwargs):
        won = [c.trade for c in contracts]
        schedules = {}
        for trade in won:
            for vessel in self.fleet:
                schedule = schedules.get(vessel, vessel.schedule).copy()
                schedule.add_transportation(trade)       # put the trade at the end
                if schedule.verify_schedule():           # can the ship make the time windows?
                    schedules[vessel] = schedule
                    break
            else:
                print("could not fit", trade.origin_port.name, "->", trade.destination_port.name)
        self.apply_schedules(schedules)
```

**Run it. You should see** lots of `could not fit` lines, and a **penalty of about 16,000** in the metrics file.
**Lesson:** you won trades your ships couldn't reach in time. Never bid on a trade you can't deliver.

---

## Step 3: only bid on what fits
Move the "first ship it fits on" loop into its own method, and use it in **both** functions:

```python
    def plan(self, trades):
        schedules, fitted = {}, []
        for trade in trades:
            for vessel in self.fleet:
                schedule = schedules.get(vessel, vessel.schedule).copy()
                schedule.add_transportation(trade)
                if schedule.verify_schedule():
                    schedules[vessel] = schedule
                    fitted.append(trade)
                    break
        return schedules, fitted

    def inform(self, trades, *args, **kwargs):
        _, fitted = self.plan(trades)
        return [Bid(amount=self.trade_cost(t) * (1 + self.MARGIN), trade=t) for t in fitted]

    def receive(self, contracts, auction_ledger=None, *args, **kwargs):
        schedules, _ = self.plan([c.trade for c in contracts])
        self.apply_schedules(schedules)
```

**Run it. You should see** `bidding on 1–3` each month and **penalty 0**.
**Lesson:** you now have a complete, safe agent. Everything after this is about making more money.

---

## Step 4: see how you did
Open the newest `metrics_competition_*.json`. The quickest ways to read it:
- Run `.venv/Scripts/mable overview metrics_competition_<number>.json`, which prints income per company.
- Open [Agent Lens](https://claude.ai/artifact/FqM2hhS8QH8d1MwCa5uvKe), go to "Run lens" and drop the file in. You'll get the charts.

Things worth checking:
- **Penalty:** must be 0.
- **Wins:** if you win nothing, your bids are too high. If you win everything but lose money, they're too low.
- **Income versus the rival:** this is what decides your ranking.

---

## Step 5: make it smarter (one idea at a time, re-run after each)
These are the upgrades the finished `group19.py` makes, in order of how much they helped:

1. **Price the extra cost, not the whole trip.** Cost = fuel(ship's plan *with* the trade) − fuel(plan *without* it). A trade that starts where a ship already ends up is nearly free. *(`marginal_cost` in group19.py)*
2. **Try every slot, not just the end.** Use `schedule.get_insertion_points()` and `add_transportation(trade, pick_up_slot, drop_off_slot)` to slot the trade in where it's cheapest. *(`best_insertion`)*
3. **Give each trade to the cheapest ship, not the first.** Keep picking the cheapest (trade, ship) pair until nothing fits. *(`propose_schedules`)*
4. **Watch the clock.** MABLE stops you after 60 s. `verify_schedule` is slow, so check the cheap options first. *(`route_cost`, `MAX_VERIFY`)*
5. **Tune `MARGIN`.** Try 0.0, 0.2, 0.4 and 1.0 with `sweep.py`. If no rival bids on a trade, MABLE pays you your own bid, so a higher margin is pure profit there.

Mistakes that cost us time (from `bidding.md`):
- **An error inside `receive` doesn't crash anything.** It just shows up later as a penalty. If you see a penalty, add `print`s in `receive`.
- **Adding new trades to a ship that is already busy caused crazy fuel bills.** Give new trades only to ships with an empty `vessel.schedule`.

---

## When you're done with a step
- Make each change small, run, and look at the numbers.
- Write one line in your design journal: what you changed, why, and what the number did. That line goes straight into the report.
