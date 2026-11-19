import os
import math
import inspect

from mable.cargo_bidding import TradingCompany
from mable.examples import environment, fleets
from mable.transport_operation import ScheduleProposal


class Company19(TradingCompany):

    # Could be overriden but isn't necessary at this time
    def pre_inform(self, trades, time):
        pass
    
    # Used to create possible schedules
    # Pre-scheduling part
    def propose_schedules(self, trades):
        schedules = {}
        costs = {}
        scheduled_trades = []

        for current_trade in trades:
            result = self.find_lowest_cost_schedule(current_trade, schedules)
            if result is None:
                continue
            
            vessel, schedule, cost = result
            schedules[vessel] = schedule
            costs[current_trade] = cost
            scheduled_trades.append(current_trade)

        print(f"[propose] {len(trades)} trades in, {len(scheduled_trades)} scheduled")
        return ScheduleProposal(schedules, scheduled_trades, costs)

    # Finds and returns a vessel, schedule and cost for a given trade which has the lowest schedule cost
    def find_lowest_cost_schedule(self, current_trade, schedules):
        lowest_cost = math.inf
        best = None

        for vessel in self._fleet:
            current_schedule = schedules.get(vessel, vessel.schedule)
            new_schedule = current_schedule.copy()
            new_schedule.add_transportation(current_trade)

            if new_schedule.verify_schedule():
                cost = self.calculate_marginal_cost(vessel, current_schedule, current_trade)

                if cost < lowest_cost:
                    lowest_cost = cost
                    best = (vessel, new_schedule, cost)

        return best

    # Calculates the cost of a vessel to carry out a specified trade given its current schedule
    def calculate_marginal_cost(self, vessel, schedule, trade):
        start_port = self.get_last_port(vessel, schedule)

        # Ballast leg
        if start_port == trade.origin_port:
            ballast_cost = 0
        else:
            ballast_distance = self.headquarters.get_network_distance(start_port, trade.origin_port)
            ballast_time = vessel.get_travel_time(ballast_distance)
            ballast_cost = vessel.get_ballast_consumption(ballast_time, vessel.speed)

        # Loading and unloading
        loading_time = vessel.get_loading_time(trade.cargo_type, trade.amount)
        loading_costs = vessel.get_loading_consumption(loading_time)
        unloading_costs = vessel.get_unloading_consumption(loading_time)

        # Travelling
        travel_distance = self.headquarters.get_network_distance(trade.origin_port, trade.destination_port)
        travel_time = vessel.get_travel_time(travel_distance)
        travel_cost = vessel.get_laden_consumption(travel_time, vessel.speed)
        cost = ballast_cost + loading_costs + unloading_costs + travel_cost
        return cost

    # Gets the last port of a given schedule
    def get_last_port(self, vessel, schedule):
        stops = schedule.get_simple_schedule()
        if stops:
            kind, trade = stops[-1]
            return trade.destination_port
        return vessel.location


    def receive(self, contracts, auction_ledger=None, *args, **kwargs):
        print(f"[receive] won {len(contracts)} contracts")
        super().receive(contracts, auction_ledger, *args, **kwargs)

if __name__ == '__main__':
    os.makedirs("outputs", exist_ok=True)
    print(inspect.getsource(TradingCompany.inform))

    specifications_builder = environment.get_specification_builder(environment_files_path=".")
    fleet = fleets.example_fleet_1()
    specifications_builder.add_company(Company19.Data(Company19, fleet, "Company 19"))
    sim = environment.generate_simulation(specifications_builder, output_directory="outputs")
    sim.run()
