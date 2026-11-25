import os
import math
import inspect

from mable.cargo_bidding import TradingCompany
from mable.examples import environment, fleets
from mable.transport_operation import ScheduleProposal, Bid


class Company19(TradingCompany):
    
    # Could be overriden but isn't necessary at this time
    def pre_inform(self, trades, time):
        pass

    def inform(self, trades, *args, **kwargs):
        proposal = self.propose_schedules(trades)
        self._estimates = getattr(self, "_estimates", {})
        self._n_bids = getattr(self, "_n_bids", 0)
        bids = []

        for trade in proposal.scheduled_trades:
            cost = proposal.costs.get(trade, 0)
            self._estimates[trade] = cost
            self._n_bids += 1
            print(f"[bid] {trade}: estimate {cost:.2f}")
            bids.append(Bid(amount=cost * 1.1, trade=trade))
        return bids
    
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
            old_schedule = schedules.get(vessel, vessel.schedule)

            schedules[vessel] = schedule

            delta = self.schedule_cost(vessel, schedule) - self.schedule_cost(vessel, old_schedule)
            print(f"schedule_cost delta={delta:.2f}  marginal={cost:.2f}")

            costs[current_trade] = cost
            scheduled_trades.append(current_trade)

        print(f"[propose] {len(trades)} trades in, {len(scheduled_trades)} scheduled")
        return ScheduleProposal(schedules, scheduled_trades, costs)

    # Finds and returns a vessel, schedule and cost for a given trade which has the lowest schedule cost
    def find_lowest_cost_schedule(self, current_trade, schedules):
        lowest_delta = math.inf
        best = None

        for vessel in self._fleet:
            current_schedule = schedules.get(vessel, vessel.schedule)
            old_cost = self.schedule_cost(vessel, current_schedule)
            insertion_points = current_schedule.get_insertion_points()

            for k in range(len(insertion_points)):
                idx_pick_up = insertion_points[k]

                for idx_drop_off in insertion_points[k:]:
                    candidate = current_schedule.copy()
                    candidate.add_transportation(current_trade, idx_pick_up, idx_drop_off)

                    if not candidate.verify_schedule():
                        continue

                    delta = self.schedule_cost(vessel, candidate) - old_cost
                    if delta < lowest_delta:
                        lowest_delta = delta
                        best = (vessel, candidate, delta)

        return best

    # Returns the cost of an entire schedule
    def schedule_cost(self, vessel, schedule):
        stops = schedule.get_simple_schedule()
        pos = vessel.location
        total, active_time = 0.0, 0.0
        onboard = 0

        for kind, trade in stops:
            target = trade.origin_port if kind == 'PICK_UP' else trade.destination_port

            if pos != target:
                distance = self.headquarters.get_network_distance(pos, target)
                t = vessel.get_travel_time(distance)
                if onboard > 0:
                    total += vessel.get_laden_consumption(t, vessel.speed)
                else:
                    total += vessel.get_ballast_consumption(t, vessel.speed)
                
                active_time += t

            load_time = vessel.get_loading_time(trade.cargo_type, trade.amount)
            if kind == 'PICK_UP':
                total += vessel.get_loading_consumption(load_time)
                onboard += 1
            else:
                total += vessel.get_unloading_consumption(load_time)
                onboard -= 1

            active_time += load_time
            pos = target

        return total # - vessel.get_idle_consumption(active_time)

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
        
        print(f"  start={start_port} ({type(start_port).__name__}) origin={trade.origin_port} dest={trade.destination_port}")
        print(f"  ballast={ballast_cost:.2f} loading={loading_costs:.2f} "
              f"unloading={unloading_costs:.2f} laden={travel_cost:.2f} total={cost:.2f}")
        
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
    # print(inspect.getsource(TradingCompany.inform))

    specifications_builder = environment.get_specification_builder(environment_files_path=".")
    fleet = fleets.example_fleet_1()
    specifications_builder.add_company(Company19.Data(Company19, fleet, "Company 19"))
    sim = environment.generate_simulation(specifications_builder, output_directory="outputs")
    sim.run()


# Attempt 1:
""" start=Port<Aberdeen-f8ea5ddd09c3 (57.14151, -2.07729)> (LatLongPort) origin=Port<Port Said-73e707725c62 (31.25094, 32.30507)> dest=Port<Tanjung Pelepas-71ae886ba35d (1.34033, 103.54542)>
ballast=745.68 loading=8.87 unloading=76.77 laden=2708.43 total=3539.75
[propose] 1 trades in, 1 scheduled
[bid] TimeWindowTrade(origin_port=Port<Port Said-73e707725c62 (31.25094, 32.30507)>, destination_port=Port<Tanjung Pelepas-71ae886ba35d (1.34033, 103.54542)>, amount=68561.73410929955, cargo_type='Oil', time=1440, probability=1, status=<TradeStatus.UNKNOWN: 1>, time_window=[1776, 2016, 2208, 2448]): estimate 3539.75
[receive] won 1 contracts
start=Port<Aberdeen-f8ea5ddd09c3 (57.14151, -2.07729)> (LatLongPort) origin=Port<Port Said-73e707725c62 (31.25094, 32.30507)> dest=Port<Tanjung Pelepas-71ae886ba35d (1.34033, 103.54542)>
ballast=745.68 loading=8.87 unloading=76.77 laden=2708.43 total=3539.75
[propose] 1 trades in, 1 scheduled """
""" +---------+----------+
|   Name  |    Value |
+---------+----------+
|   Cost  | 4007.075 |
| Penalty |        0 |
| Revenue |  3539.75 |
+---------+----------+
|  Income | -467.325 |
+---------+----------+ """


# Attempt 2 - skip first auction
""" start=Port<Aberdeen-f8ea5ddd09c3 (57.14151, -2.07729)> (LatLongPort) origin=Port<Port Said-73e707725c62 (31.25094, 32.30507)> dest=Port<Tanjung Pelepas-71ae886ba35d (1.34033, 103.54542)>
  ballast=745.68 loading=8.87 unloading=76.77 laden=2708.43 total=3539.75
[propose] 1 trades in, 1 scheduled
[bid] TimeWindowTrade(origin_port=Port<Port Said-73e707725c62 (31.25094, 32.30507)>, destination_port=Port<Tanjung Pelepas-71ae886ba35d (1.34033, 103.54542)>, amount=68561.73410929955, cargo_type='Oil', time=1440, probability=1, status=<TradeStatus.UNKNOWN: 1>, time_window=[1776, 2016, 2208, 2448]): estimate 3539.75
[receive] won 1 contracts
  start=Port<Aberdeen-f8ea5ddd09c3 (57.14151, -2.07729)> (LatLongPort) origin=Port<Port Said-73e707725c62 (31.25094, 32.30507)> dest=Port<Tanjung Pelepas-71ae886ba35d (1.34033, 103.54542)>
  ballast=745.68 loading=8.87 unloading=76.77 laden=2708.43 total=3539.75
[propose] 1 trades in, 1 scheduled """

""" +---------+----------+
|   Name  |    Value |
+---------+----------+
|   Cost  | 4007.075 |
| Penalty |        0 |
| Revenue |  3539.75 |
+---------+----------+
|  Income | -467.325 |
+---------+----------+ """