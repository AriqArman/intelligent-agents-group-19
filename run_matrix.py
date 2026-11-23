import itertools, csv, os
from mable.examples import environment, fleets, companies
from group19 import Company19

def run(num_trades, fleet_fn, opponent_cls, n_opp, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    spec = environment.get_specification_builder(
        environment_files_path=".",
        trades_per_occurrence=num_trades,
        num_auctions=12,
    )
    spec.add_company(Company19.Data(Company19, fleet_fn(), "Company 19"))

    for i in range(n_opp):
        spec.add_company(opponent_cls.Data(opponent_cls, fleet_fn(), f"Opp {i}"))

    sim = environment.generate_simulation(spec, output_directory=out_dir)
    sim.run()

if __name__ == "__main__":
    fleet_fns = [fleets.example_fleet_1, fleets.example_fleet_2, fleets.example_fleet_3]
    opponents = [companies.MyArchEnemy, companies.TheScheduler]
    for trades, ffn, opp, n_opp in itertools.product([5, 20, 50, 140], fleet_fns, opponents, [1, 3]):
        out = f"outputs/t{trades}_{ffn.__name__}_{opp.__name__}_{n_opp}"
        run(trades, ffn, opp, n_opp, out)