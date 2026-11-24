import sys

from loguru import logger
from mable.examples import environment, fleets, companies

import greedy

# Removes most of the annoying DEBUG messages
logger.remove()
logger.add(sys.stderr, level="INFO")

def build_specification():
    number_of_months = 2
    trades_per_auction = 2
    # Finds mable_resources.zip, which I'm guessing is used to make random trade routes
    specifications_builder = environment.get_specification_builder(
        environment_files_path=".",
        trades_per_occurrence=trades_per_auction,
        num_auctions=number_of_months)
    # Creates fleet of ships of the given number, and random positions and names
    my_fleet = fleets.mixed_fleet(num_suezmax=1, num_aframax=0, num_vlcc=0)
    # Adds fleet and code for how the company works
    specifications_builder.add_company(greedy.Companyn.Data(greedy.Companyn, my_fleet, greedy.Companyn.__name__))
    # Adds default example companies to compete
    arch_enemy_fleet = fleets.mixed_fleet(num_suezmax=1, num_aframax=0, num_vlcc=0)
    specifications_builder.add_company(
        companies.MyArchEnemy.Data(
            companies.MyArchEnemy, arch_enemy_fleet, "Arch Enemy Ltd.",
            profit_factor=1.5))
    # the_scheduler_fleet = fleets.mixed_fleet(num_suezmax=1, num_aframax=1, num_vlcc=1)
    # specifications_builder.add_company(
    #     companies.TheScheduler.Data(
    #         companies.TheScheduler, the_scheduler_fleet, "The Scheduler LP",
    #         profit_factor=1.4))
    sim = environment.generate_simulation(
        specifications_builder,
        show_detailed_auction_outcome=True,
        global_agent_timeout=60)
    sim.run()

if __name__ == '__main__':
    build_specification()
