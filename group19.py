import os

from mable.cargo_bidding import TradingCompany
from mable.examples import environment, fleets
from mable.transport_operation import ScheduleProposal, Bid


class Company19(TradingCompany):

    # Could be overriden but isn't necessary at this time
    def pre_inform(self, trades, time):
        pass

    # Turns the costs from propose_schedules into bid amounts (cost + profit margin)
    # Should override for more complex bidding and pricing strategies
    def inform(self, trades, *args, **kwargs):
        proposed = self.propose_schedules(trades)
        bids = []

        for trade in proposed.scheduled_trades:
            cost = proposed.costs.get(trade)
            if cost is None:
                continue
            bids.append(Bid(amount=cost * 1.1, trade=trade))
        return bids
    
    # Used to create possible schedules
    # Pre-scheduling part
    def propose_schedules(self, trades):
        schedules = {}
        costs = {}
        scheduled_trades = []

        # TODO

        return ScheduleProposal(schedules, scheduled_trades, costs)

    # Recomputes the schedules for won traders by running propose_schedules again
    # May want to override this for a custom post-scheduling module
    def receive(self, contracts, auction_ledger=None, *args, **kwargs):
        trades = [c.trade for c in contracts]
        proposal = self.propose_schedules(trades)
        rejected = self.apply_schedules(proposal.schedules)
    

if __name__ == '__main__':
    os.makedirs("outputs", exist_ok=True)

    specifications_builder = environment.get_specification_builder(environment_files_path=".")
    fleet = fleets.example_fleet_1()
    specifications_builder.add_company(Company19.Data(Company19, fleet, "Company 19"))
    sim = environment.generate_simulation(specifications_builder, output_directory="outputs")
    sim.run()
