"""
Local competitive run: Company19 vs MABLE's example agents over 12 monthly auctions.

Usage:  python run_local.py [margin] [trades_per_auction] [fleet_size]   (margin < 0 = never bid)
Then:   mable overview metrics_competition_<id>.json
"""
import sys

from mable.examples import environment, fleets, companies

from group19 import Company19

if __name__ == '__main__':
    margin = float(sys.argv[1]) if len(sys.argv) > 1 else Company19.MARGIN
    trades_per_auction = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    fleet_size = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    attrs = {"MARGIN": margin}
    if margin < 0:  # baseline: never bid, so the company only pays idle fuel
        attrs["inform"] = lambda self, trades, *a, **k: []
    Tuned = type("Company19", (Company19,), attrs)

    builder = environment.get_specification_builder(
        environment_files_path=".", trades_per_occurrence=trades_per_auction, num_auctions=12)
    builder.add_company(Tuned.Data(Tuned, fleets.mixed_fleet(num_suezmax=fleet_size), f"Group 19 (m={margin})"))
    builder.add_company(companies.MyArchEnemy.Data(
        companies.MyArchEnemy, fleets.mixed_fleet(num_suezmax=fleet_size), "Arch Enemy Ltd."))
    builder.add_company(companies.TheScheduler.Data(
        companies.TheScheduler, fleets.mixed_fleet(num_suezmax=fleet_size), "The Scheduler LP"))
    sim = environment.generate_simulation(builder, info={"margin": margin})
    sim.run()
