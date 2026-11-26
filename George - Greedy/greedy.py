import math
import random

from mable.cargo_bidding import TradingCompany, VesselWithEngine
from mable.transport_operation import Bid, Schedule
from mable.shipping_market import Contract, Port, TimeWindowTrade

from print_to_file import print # lazy way to make all prints go to file rather than command line

# Number of best schedules to do analysis on
SELECTIONS = 5
# Number of iterations for the greedy algorithm
ITERATIONS = 100
# Proportion of the best schedules a trade must be in to be considered
PROPORTION_TO_BID = 0.5

class Companyn(TradingCompany):
    def pre_inform(self, trades: list[TimeWindowTrade], time: int) -> None:
        print("pre_inform trades:", trades)
        print("pre_inform time:", time)
        pass

    def inform(self, trades: list[TimeWindowTrade], *args, **kwargs) -> list[Bid]:
        print("inform trades:", trades)
        proposals = self.random_greedy_proposals(trades, SELECTIONS, ITERATIONS)
        print("inform proposals:", proposals)
        print("inform proposals count:", len(proposals))
        # Calculates the trade count and total (for the average) costs of each trade over the cheapest few journeys
        trade_counts: dict[TimeWindowTrade, float] = {}
        trade_costs: dict[TimeWindowTrade, float] = {}
        for proposal in proposals:
            for trade, cost in proposal[2].items():
                if trade_counts.get(trade) is None:
                    trade_counts[trade] = 1
                    trade_costs[trade] = cost
                else:
                    trade_counts[trade] += 1
                    trade_costs[trade] += cost
        trades_to_bid = [trade for trade in trade_counts.keys() if trade_counts[trade] >= SELECTIONS * PROPORTION_TO_BID]
        # Factors in the cost of each individual trade if it was the only one won
        bid_amounts = {}
        for trade in trades_to_bid:
            current_schedules: dict[VesselWithEngine, Schedule] = {}
            for vessel in self.fleet:
                current_schedules[vessel] = vessel.schedule.copy()
            single_journey_cost = self.trade_cost_on_any_vessel(current_schedules, trade)
            if single_journey_cost[0] is not None:
                bid_amounts[trade] = (single_journey_cost[1] + trade_costs[trade] / trade_counts[trade]) / 2
        bids = [Bid(amount=cost, trade=trade) for trade, cost in bid_amounts.items()]
        print("inform bids:", bids)
        return bids

    def receive(self, contracts: list[Contract], auction_ledger: dict[str, list[Contract]], *args, **kwargs) -> None:
        print("receive contracts:", contracts)
        print("receive auction_ledger:", auction_ledger)
        trades: list[TimeWindowTrade] = [one_contract.trade for one_contract in contracts] # type: ignore
        schedules = self.random_greedy_proposals(trades, 1, ITERATIONS)[0][1]
        print("receive proposals:", schedules)
        self.apply_schedules(schedules)

    def schedule_cost(self, vessel: VesselWithEngine, schedule: Schedule) -> float:
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
            distance_to_next = self.headquarters.get_network_distance(previous_port, next_port) # type: ignore
            previous_port = next_port
            time_to_next = vessel.get_travel_time(distance_to_next)
            total_time += time_to_next
            try: speed = distance_to_next / time_to_next
            except: speed = 0
            if load_count == 0:
                total_fuel += vessel.get_ballast_consumption(time_to_next, speed)
            else:
                total_fuel += vessel.get_laden_consumption(time_to_next, speed)

            # Loading/unloading costs
            loading_time = vessel.get_loading_time(trade.cargo_type, trade.amount)
            total_time += loading_time
            if action == "PICK_UP":
                total_fuel += vessel.get_loading_consumption(loading_time)
            else:
                total_fuel += vessel.get_unloading_consumption(loading_time)

        # Idle costs
        # Calculates cost relative to the cost of a vessel being idle, rather than the true idle costs
        # This makes it independent of the length of each trade period
        total_fuel -= vessel.get_idle_consumption(total_time)

        return vessel.get_cost(total_fuel)

    def trade_cost_on_vessel(self, vessel: VesselWithEngine, current_schedule: Schedule, new_trade: TimeWindowTrade) -> tuple[Schedule | None, float]:
        """Calculates the additional cost of adding new_trade at each point in the schedule.
        Returns the cheapest schedule found with that trade (or None if none are valid) and the cost increase."""
        # NOTE: currently checks the cost of the whole schedule each time, could be made more efficient by adding only local changes
        insertion_points = current_schedule.get_insertion_points()
        best_schedule: Schedule | None = None
        best_cost = math.inf
        for pick_up_index in range(len(insertion_points)):
            pick_up = insertion_points[pick_up_index]
            for drop_off_index in range(pick_up_index, len(insertion_points)):
                drop_off = insertion_points[drop_off_index]
                new_schedule = current_schedule.copy()
                new_schedule.add_transportation(new_trade, pick_up, drop_off)
                if new_schedule.verify_schedule():
                    print("Verified")
                    new_cost = self.schedule_cost(vessel, new_schedule)
                    if new_cost < best_cost:
                        best_schedule = new_schedule
                        best_cost = new_cost
        return best_schedule, best_cost

    def trade_cost_on_any_vessel(self, current_schedules: dict[VesselWithEngine, Schedule], new_trade: TimeWindowTrade) -> tuple[dict[VesselWithEngine, Schedule] | None, float]:
        """Uses trade_cost_on_vessel to find the cost of adding the trade to each vessel.
        Returns the schedules with the trade added to the cheapest one, and cost added."""
        vessels: list[VesselWithEngine] = list(current_schedules.keys())
        best_change: tuple[VesselWithEngine, Schedule] | None = None
        best_cost = math.inf
        for vessel in vessels:
            new_schedule, new_cost = self.trade_cost_on_vessel(vessel, current_schedules[vessel], new_trade)
            if new_schedule is not None:
                if new_cost < best_cost:
                    best_change = (vessel, new_schedule)
                    best_cost = new_cost

        if best_change is not None:
            new_schedules = current_schedules.copy()
            new_schedules[best_change[0]] = best_change[1]
            return new_schedules, best_cost
        else:
            return None, best_cost

    def generate_cheapest_schedules(self, vessels: list[VesselWithEngine], trades: list[TimeWindowTrade], selections: int, iterations: int) -> list[tuple[float, dict[VesselWithEngine, Schedule] | None, dict[TimeWindowTrade, float] | None]]:
        """Iteratively adds new trades in a random order.
        Uses trade_cost_on_any_vessel to find the cheapest position for each new trade.
        Adds as many trades as possible.
        If the result is within the top 'selections' cheapest schedules, saves it to a list.
        Repeats 'iterations' times and returns the list of cheapest schedules."""
        current_schedules: dict[VesselWithEngine, Schedule] = {}
        for vessel in vessels:
            current_schedules[vessel] = vessel.schedule.copy()
        current_cost = 0
        for vessel in vessels:
            current_cost += self.schedule_cost(vessel, current_schedules[vessel])

        # Structure: [(total_cost, {vessel: schedule}, {trade: cost})]
        best_proposals: list[tuple[float, dict[VesselWithEngine, Schedule] | None, dict[TimeWindowTrade, float] | None]] = [(math.inf, None, None)]

        for i in range(iterations):
            shuffled_trades = random.sample(trades, len(trades))
            print("shuffled_trades:", shuffled_trades)
            new_schedules = current_schedules.copy()
            new_cost = 0
            new_trade_costs = {}
            # Generates schedule from greedily adding trades to cheapest vessel
            for trade in shuffled_trades:
                print("evaluating trade:", trade)
                candidate_schedules, added_cost = self.trade_cost_on_any_vessel(new_schedules, trade)
                try: print("candidate_schedules:", [(vessel.name, schedule.get_simple_schedule()) for vessel, schedule in candidate_schedules.items()]) # type: ignore
                except: print("candidate_schedules:", candidate_schedules)
                print("added_cost:", added_cost)
                if candidate_schedules is not None:
                    new_schedules = candidate_schedules
                    new_cost += added_cost
                    new_trade_costs[trade] = added_cost
            # If new cost is cheap enough, adds to list of cheapest trades
            if new_cost < best_proposals[-1][0]:
                print("current best_proposals:", best_proposals)
                print("cheaper candidate:", [(vessel.name, schedule.get_simple_schedule()) for vessel, schedule in new_schedules.items()])
                print("cheaper cost:", new_cost)
                for i, proposal in enumerate(best_proposals):
                    # If new cost is cheaper, inserts here
                    if new_cost < proposal[0]:
                        best_proposals.insert(i, (new_cost, new_schedules, new_trade_costs))
                        break
                    # If new cost is equal, checks if it already exists first
                    elif new_cost == proposal[0]:
                        unique = True
                        for prop in best_proposals:
                            if [(vessel.name, schedule.get_simple_schedule()) for vessel, schedule in prop[1].items()] == [(vessel.name, schedule.get_simple_schedule()) for vessel, schedule in new_schedules.items()]: # type: ignore
                                print("not unique:", prop[1])
                                unique = False
                                break
                        if unique:
                            best_proposals.insert(i, (new_cost, new_schedules, new_trade_costs))
                        break
                if len(best_proposals) > selections:
                    best_proposals = best_proposals[:selections]

        return best_proposals

    def random_greedy_proposals(self, trades: list[TimeWindowTrade], selections: int, iterations: int) -> list[tuple[float, dict[VesselWithEngine, Schedule], dict[TimeWindowTrade, float]]]:
        vessels: list[VesselWithEngine] = self.fleet
        print("proposal vessels:", vessels)
        best_proposals = self.generate_cheapest_schedules(vessels, trades, selections, iterations)
        # Removes placeholder None at the end of the list if less than 'selections' viable schedules have been found
        if best_proposals[-1][1] is None:
            best_proposals.pop(-1)
        return best_proposals # type: ignore