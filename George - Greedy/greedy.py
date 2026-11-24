import math
import random

from mable.cargo_bidding import TradingCompany, VesselWithEngine
from mable.transport_operation import Bid, Schedule, ScheduleProposal
from mable.shipping_market import Contract, Port, TimeWindowTrade

class Companyn(TradingCompany):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hq = self.headquarters

    def pre_inform(self, trades: list[TimeWindowTrade], time: int) -> None:
        print("pre_inform trades:", trades)
        print("pre_inform time:", time)
        pass

    def inform(self, trades: list[TimeWindowTrade], *args, **kwargs) -> list[Bid]:
        print("inform trades:", trades)
        proposed_scheduling = self.propose_schedules(trades)
        scheduled_trades = proposed_scheduling.scheduled_trades
        trades_and_costs = [
            (x, max(100000, proposed_scheduling.costs[x])) if x in proposed_scheduling.costs
            else (x, 100000)
            for x in scheduled_trades]
        bids = [Bid(amount=cost, trade=one_trade) for one_trade, cost in trades_and_costs]
        return bids

    def receive(self, contracts: list[Contract], auction_ledger: dict[str, list[Contract]] = None, *args, **kwargs) -> None:
        print("receive contracts:", contracts)
        print("receive auction_ledger:", auction_ledger)
        trades = [one_contract.trade for one_contract in contracts]
        scheduling_proposal = self.propose_schedules(trades)
        self.apply_schedules(scheduling_proposal.schedules)

    def vessel_get_costs(self, vessel: VesselWithEngine, schedule: Schedule) -> float:
        """Calculates the total cost of the schedule (minus the idle costs of the vessel doing nothing)."""
        # Loading/unloading costs
        total_time = 0
        total_fuel = 0
        load_count = 0
        previous_port = vessel.location
        simple_schedule: list[tuple[str, TimeWindowTrade]] = schedule.get_simple_schedule() # type: ignore

        for point in simple_schedule:
            action: str = point[0]
            trade: TimeWindowTrade = point[1]
            if action == "PICK_UP":
                next_port: Port = trade.origin_port # type: ignore
                load_count += 1
            else:
                next_port: Port = trade.destination_port # type: ignore
                load_count -= 1

            # Travel costs
            distance_to_next = self.hq.get_network_distance(previous_port, next_port)
            previous_port = next_port
            time_to_next = vessel.get_travel_time(distance_to_next)
            total_time += time_to_next
            if load_count == 0:
                total_fuel += vessel.get_ballast_consumption(time_to_next, distance_to_next / time_to_next)
            else:
                total_fuel += vessel.get_laden_consumption(time_to_next, distance_to_next / time_to_next)

            # Loading/unloading costs
            loading_time = vessel.get_loading_time(trade.cargo_type, trade.amount)
            total_time += loading_time
            if action == "PICK_UP":
                total_fuel = vessel.get_loading_consumption(loading_time)
            else:
                total_fuel = vessel.get_unloading_consumption(loading_time)

        # Idle costs
        # Equivalent to subtracting the additional idle costs the vessel would pay if it wasn't doing work
        # True idle costs would be equal to this plus the idle cost of an always stationary vessel
        # This method instead calculates cost relative to the cost of a vessel being idle
        # This method is not dependent on the length of the current time window
        total_fuel -= vessel.get_idle_consumption(total_time)

        return vessel.get_cost(total_fuel)

    def vessel_add_cost(self, vessel: VesselWithEngine, current_schedule: Schedule, new_trade: TimeWindowTrade) -> tuple[Schedule | None, float]:
        """Calculates the additional cost of adding new_trade at each point in the schedule.
        Returns the cheapest schedule found with that trade (or None if none are valid) and the cost increase."""
        # NOTE: currently checks the cost of the whole schedule each time, could be made more efficient by adding only local changes
        insertion_points = current_schedule.get_insertion_points()
        best_schedule: Schedule | None = None
        best_cost = math.inf
        for pick_up in range(len(insertion_points)):
            for drop_off in range(pick_up, len(insertion_points)):
                new_schedule = current_schedule.copy()
                new_schedule.add_transportation(new_trade, pick_up, drop_off)
                if new_schedule.verify_schedule():
                    new_cost = self.vessel_get_costs(vessel, new_schedule)
                    if new_cost < best_cost:
                        best_schedule = new_schedule
                        best_cost = new_cost
        return best_schedule, best_cost

    def trade_add_cost(self, current_schedules: dict[VesselWithEngine, Schedule], new_trade: TimeWindowTrade, reject_cost: float) -> tuple[dict[VesselWithEngine, Schedule] | None, float]:
        """Uses vessel_add_cost to find the cost of adding the trade to each vessel.
        Returns the schedules with the trade added to the cheapest one, and cost added, or None if the minimum cost is above reject_cost."""
        vessels: list[VesselWithEngine] = list(current_schedules.keys())
        best_change: tuple[VesselWithEngine, Schedule] | None = None
        best_cost = math.inf
        for vessel in vessels:
            new_schedule, new_cost = self.vessel_add_cost(vessel, current_schedules[vessel], new_trade)
            if new_schedule is not None:
                if new_cost < best_cost and new_cost < reject_cost:
                    best_change = (vessel, new_schedule)
                    best_cost = new_cost

        if best_change is not None:
            new_schedules = current_schedules.copy()
            new_schedules[best_change[0]] = best_change[1]
            return new_schedules, best_cost
        else:
            return None, best_cost

    def generate_cheapest_schedule(self, vessels: list[VesselWithEngine], trades: list[TimeWindowTrade], reject_cost: float, iterations: int) -> tuple[dict[VesselWithEngine, Schedule], float, dict[TimeWindowTrade, float]]:
        """Iteratively adds new trades in a random order.
        Uses trade_add_cost to find the cheapest position for each new trade.
        Adds as many trades as possible.
        Repeats iterations times and returns the cheapest found schedule."""
        # Reject cost lines up well with payment or payment + penalty
        current_schedules: dict[VesselWithEngine, Schedule] = {}
        for vessel in vessels:
            current_schedules[vessel] = vessel.schedule.copy()
        current_cost = 0
        for vessel in vessels:
            current_cost += self.vessel_get_costs(vessel, current_schedules[vessel])

        overall_best_schedules = current_schedules
        overall_best_cost = current_cost
        overall_trade_costs = {}

        for i in range(iterations):
            shuffled_trades = random.sample(trades, len(trades))
            new_schedules = current_schedules.copy()
            new_cost = current_cost
            new_trade_costs = {}
            for trade in shuffled_trades:
                candidate_schedules, added_cost = self.trade_add_cost(new_schedules, trade, reject_cost)
                if candidate_schedules is not None:
                    new_schedules = candidate_schedules
                    new_cost += added_cost
                    new_trade_costs[trade] = added_cost
            if new_cost < overall_best_cost:
                overall_best_schedules = new_schedules
                overall_best_cost = new_cost
                overall_trade_costs = new_trade_costs

        return overall_best_schedules, overall_best_cost, overall_trade_costs

    def propose_schedules(self, trades: list[TimeWindowTrade]) -> ScheduleProposal:
        vessels: list[VesselWithEngine] = self._fleet
        print("propose_schedules trades:", trades)
        print("propose_schedules vessels:", vessels)

        schedules, _, trade_costs = self.generate_cheapest_schedule(vessels, trades, math.inf, 1000)
        scheduled_trades = list(trade_costs.keys())
        return ScheduleProposal(schedules, scheduled_trades, trade_costs) # type: ignore