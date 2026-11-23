import itertools, csv, os, glob, subprocess
from mable.examples import environment, fleets, companies
from ALNS import Company19

# Performs a run of the algorithm with a given number of trades, fleet and opponents
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
    write_overview(out_dir)

# Automatically writes the overview (cost, penalty, revenue) to a txt file alongside the JSON
def write_overview(out_dir):
    for json_path in glob.glob(os.path.join(out_dir, "*.json")):
        txt_path = os.path.splitext(json_path)[0] + "_overview.txt"
        result = subprocess.run(
            ["mable", "overview", json_path],
            capture_output=True, text=True,
        )
        with open (txt_path, "w", encoding="utf-8") as f:
            f.write(result.stdout)
            if result.returncode != 0:
                f.write("\n--- ERROR ---\n" + result.stderr)

# Runs Matrix tests on the agent
# Performs a run on each combination of fleet, opponent, number of trades, and number of opponents
if __name__ == "__main__":
    fleet_fns = [fleets.example_fleet_1, fleets.example_fleet_2, fleets.example_fleet_3]
    opponents = [companies.MyArchEnemy, companies.TheScheduler]
    for trades, ffn, opp, n_opp in itertools.product([5, 20, 50, 140], fleet_fns, opponents, [1, 3]):
        out = f"test_outputs/t{trades}_{ffn.__name__}_{opp.__name__}_{n_opp}"
        run(trades, ffn, opp, n_opp, out)