"""
Runs YOUR practice agent (my_agent.py) against one example rival for 6 months.
See docs/notes/start-here.md. Usage:  python run_mine.py
"""
from mable.examples import environment, fleets, companies

from my_agent import Company19

if __name__ == '__main__':
    builder = environment.get_specification_builder(
        environment_files_path=".", trades_per_occurrence=5, num_auctions=6)
    builder.add_company(Company19.Data(Company19, fleets.mixed_fleet(num_suezmax=2), "Group 19 (mine)"))
    builder.add_company(companies.MyArchEnemy.Data(
        companies.MyArchEnemy, fleets.mixed_fleet(num_suezmax=2), "Arch Enemy Ltd."))
    environment.generate_simulation(builder).run()
