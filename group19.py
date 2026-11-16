"""
Company19 - COMP6203 tramp-shipping trading agent (Group 19).

Bidding (owner: Ariq)
---------------------
Each cargo auction is a reverse second-price sealed-bid auction: the lowest bid
wins and the winner is paid the *second-lowest* bid. Our bid for a trade is

    bid = marginal_cost(trade) * (1 + MARGIN)

where marginal_cost is the extra fuel cost of fitting the trade into the
cheapest vessel's current schedule (ballast leg to the pick-up, laden leg,
loading and unloading), net of the idle fuel the vessel would have burnt anyway.
Trades that no vessel can deliver within their time windows get no bid.

Scheduling (basic placeholder until the team's scheduler is integrated)
-----------------------------------------------------------------------
Greedy cheapest insertion: repeatedly insert the (trade, vessel, position)
with the lowest marginal cost into the fleet's schedules, as long as the
schedule stays feasible (MABLE's ``verify_schedule``). The same routine
chooses the bid set (so we never bid on trades that cannot all be delivered
together) and schedules the trades we win. Only vessels with no committed
work take new trades (see ``free_vessels`` for the MABLE quirk behind this).

Ideas from the AAMAS'25 1st-place report (Mai et al., Delft): minimum-cost
insertion for pre-auction cost estimation and post-auction scheduling, and
pricing bids on marginal cost under a second-price auction. Implemented from
the ideas, not their code.
"""
import time

from loguru import logger

from mable.cargo_bidding import TradingCompany
from mable.simulation_space.universe import OnJourney
from mable.transport_operation import Bid, ScheduleProposal


class Company19(TradingCompany):
    # Bid = marginal cost * (1 + MARGIN). Override in a subclass to tune.
    MARGIN = 0.4
    # Only try the last N insertion points per schedule, to stay well inside
    # MABLE's 60 s per-call timeout when schedules get long.
    MAX_INSERTION_POINTS = 8
    # Seconds allowed for planning in inform/receive (MABLE kills a call at 60 s).
    TIME_BUDGET = 40
    STANDALONE_BUDGET = 10
    RECEIVE_BUDGET = 50
    # Pre-check tolerance (hours) on latest pick-up/drop-off, and how many
    # plausible options per (trade, vessel) get MABLE's exact verify_schedule.
    WINDOW_SLACK = 1.0
    MAX_VERIFY = 3
    max_verify = MAX_VERIFY  # receive() lifts this to "all" when a won trade does not fit

    # ------------------------------------------------------------------ market

    def inform(self, trades, *args, **kwargs):
        start = time.monotonic()
        # The joint plan picks a bid set that can all be delivered together.
        proposal = self.propose_schedules(trades, deadline=start + self.TIME_BUDGET)
        bids = []
        for trade in proposal.scheduled_trades:
            cost = proposal.costs[trade]
            # In the joint plan a trade may look cheap only because it rides on
            # another trade we might not win; price it at the dearer of the two views.
            if time.monotonic() - start < self.TIME_BUDGET + self.STANDALONE_BUDGET:
                cost = max(cost, self.standalone_cost(trade))
            bids.append(Bid(amount=cost * (1 + self.MARGIN), trade=trade))
        return bids

    def receive(self, contracts, auction_ledger=None, *args, **kwargs):
        won = [c.trade for c in contracts]
        deadline = time.monotonic() + self.RECEIVE_BUDGET
        proposal = self.propose_schedules(won, deadline=deadline)
        missed = [t for t in won if t not in proposal.scheduled_trades]
        if missed:
            # An undelivered contract is fined, so retry checking every insertion option.
            self.max_verify = None
            retry = self.propose_schedules(won, deadline=deadline)
            self.max_verify = self.MAX_VERIFY
            if len(retry.scheduled_trades) > len(proposal.scheduled_trades):
                proposal = retry
                missed = [t for t in won if t not in proposal.scheduled_trades]
        if missed:
            logger.warning(f"Company19 could not schedule {len(missed)} won trade(s): {missed}")
        self.apply_schedules(proposal.schedules)

    # -------------------------------------------------------------- scheduling

    def propose_schedules(self, trades, deadline=None):
        """Greedy cheapest insertion of ``trades`` into the fleet's schedules.

        Stops early (returning what is planned so far) once ``deadline``
        (a ``time.monotonic()`` value) has passed.
        """
        schedules = {}   # vessel -> schedule including trades inserted so far
        base = {}        # vessel -> (cost, active time) of that schedule
        options = {}     # (trade, vessel) -> (marginal cost, new schedule) | None
        costs = {}
        scheduled = []
        remaining = list(trades)

        fleet = self.free_vessels()

        def refresh(vessel):
            current = schedules.get(vessel, vessel.schedule)
            base[vessel] = self.schedule_cost(vessel, current)
            for trade in remaining:
                late = deadline is not None and time.monotonic() > deadline
                options[(trade, vessel)] = None if late else self.best_insertion(
                    vessel, current, base[vessel], trade)

        for vessel in fleet:
            refresh(vessel)

        while remaining and (deadline is None or time.monotonic() < deadline):
            best = None
            for trade in remaining:
                for vessel in fleet:
                    option = options[(trade, vessel)]
                    if option is not None and (best is None or option[0] < best[0]):
                        best = (option[0], trade, vessel, option[1])
            if best is None:
                break  # nothing left fits anywhere
            cost, trade, vessel, schedule = best
            schedules[vessel] = schedule
            costs[trade] = cost
            scheduled.append(trade)
            remaining.remove(trade)
            refresh(vessel)  # only this vessel's options changed
        return ScheduleProposal(schedules, scheduled, costs)

    def free_vessels(self):
        """Vessels with no committed work, the only ones given new trades.

        Replacing the schedule of a vessel that is already executing one makes
        MABLE restart its current leg with a shortened duration but the full
        distance, so the leg is charged at an absurd speed (fuel grows ~speed^3).
        Observed locally: one 5,000 nm leg charged ~15,000 fuel instead of ~700.
        """
        return [v for v in self.fleet if len(v.schedule) == 0]

    def standalone_cost(self, trade):
        """Marginal cost of ``trade`` alone, against the fleet's committed schedules."""
        options = [self.best_insertion(v, v.schedule, self.schedule_cost(v, v.schedule), trade)
                   for v in self.free_vessels()]
        return min((o[0] for o in options if o is not None), default=0.0)

    def best_insertion(self, vessel, schedule, base_cost, trade):
        """Cheapest feasible way to add ``trade`` to ``schedule``: (marginal cost, schedule) or None."""
        if vessel.capacity(trade.cargo_type) < trade.amount:
            return None
        tasks = schedule.get_simple_schedule()
        points = list(schedule.get_insertion_points())[-self.MAX_INSERTION_POINTS:]
        candidates = []
        for i, pick_up in enumerate(points):
            for drop_off in points[i:]:
                # Same task order MABLE's add_transportation(trade, pick_up, drop_off) produces.
                route = list(tasks)
                route.insert(pick_up - 1, ("PICK_UP", trade))
                route.insert(drop_off, ("DROP_OFF", trade))
                fuel, active, plausible = self.route_cost(vessel, route)
                if plausible:
                    candidates.append((self.marginal_cost(vessel, base_cost, (fuel, active)), pick_up, drop_off))
        # verify_schedule is expensive, so only verify the cheapest plausible options, in order.
        candidates.sort(key=lambda c: c[0])
        for cost, pick_up, drop_off in candidates[:self.max_verify]:
            candidate = schedule.copy()
            candidate.add_transportation(trade, pick_up, drop_off)
            if candidate.verify_schedule():
                return cost, candidate
        return None

    # ------------------------------------------------------- cost estimation
    # Kept separate so a teammate's scheduler can reuse or replace it.

    def marginal_cost(self, vessel, before, after):
        """Extra cost of ``after`` over ``before``, both (fuel cost, active time).

        Time spent sailing or handling cargo replaces time the vessel would
        otherwise idle (idle fuel is charged anyway), so that idle fuel is netted off.
        """
        extra_fuel = after[0] - before[0]
        extra_time = after[1] - before[1]
        idle_saved = vessel.get_cost(vessel.get_idle_consumption(extra_time))
        return max(extra_fuel - idle_saved, 0.0)

    def schedule_cost(self, vessel, schedule):
        """(fuel cost, active time) of sailing and cargo handling in ``schedule``."""
        fuel, active, _ = self.route_cost(vessel, schedule.get_simple_schedule())
        return fuel, active

    def route_cost(self, vessel, tasks):
        """Cost of a task list [("PICK_UP" | "DROP_OFF", trade), ...] for ``vessel``.

        Returns (fuel cost, active time, plausible). ``plausible`` is a cheap
        time-window/capacity check used to skip hopeless options before MABLE's
        exact (and slow) verify_schedule.
        """
        hq = self.headquarters
        location = vessel.location
        if isinstance(location, OnJourney):
            location = location.destination
        picked = {id(t) for kind, t in tasks if kind == "PICK_UP"}
        # Cargo already on board: trades dropped off here but picked up earlier.
        load = sum(t.amount for kind, t in tasks if kind == "DROP_OFF" and id(t) not in picked)
        capacity = vessel.capacity("Oil")
        clock = hq.current_time
        fuel = 0.0
        active = 0.0
        plausible = True
        for kind, trade in tasks:
            pick = kind == "PICK_UP"
            port = trade.origin_port if pick else trade.destination_port
            travel_time = vessel.get_travel_time(hq.get_network_distance(location, port))
            if load > 0:
                fuel += vessel.get_laden_consumption(travel_time, vessel.speed)
            else:
                fuel += vessel.get_ballast_consumption(travel_time, vessel.speed)
            clock += travel_time
            earliest, latest = (trade.time_window[0:2] if pick else trade.time_window[2:4])
            if earliest is not None and clock < earliest:
                clock = earliest  # wait (idle) until the window opens
            if latest is not None and clock > latest + self.WINDOW_SLACK:
                plausible = False
            handling_time = vessel.get_loading_time(trade.cargo_type, trade.amount)
            if pick:
                fuel += vessel.get_loading_consumption(handling_time)
                load += trade.amount
                if load > capacity:
                    plausible = False
            else:
                fuel += vessel.get_unloading_consumption(handling_time)
                load -= trade.amount
            clock += handling_time
            active += travel_time + handling_time
            location = port
        return vessel.get_cost(fuel), active, plausible
