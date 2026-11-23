import itertools, csv, os, glob, subprocess, random
from mable.cargo_bidding import TradingCompany
from mable.examples import environment, fleets, companies
from mable.transport_operation import Bid
from group19 import Company19

# Library TheScheduler with its bids scaled by 'scale'
class ScaledBidder(companies.TheScheduler):
    scale = 1.0

    def inform(self, trades, *args, **kwargs):
        bids = super().inform(trades, *args, **kwargs)
        return [Bid(amount=b.amount * self.scale, trade=b.trade) for b in bids]

class Underbidder(ScaledBidder): scale = 0.6    # likely loss-making
class Cautious(ScaledBidder): scale = 1.3   # high margin, wins little
class Passive(TradingCompany):  # does nothing
    def inform(self, trades, *args, **kwargs):
        return []
    def receive(self, contracts, auction_ledger=None, *args, **kwargs):
        pass

BASE_FLEETS = [fleets.example_fleet_1, fleets.example_fleet_2]
OPPONENT_POOL = [companies.MyArchEnemy, companies.TheScheduler, Underbidder, Cautious, Passive]
TRADE_COUNTS = {"small": 20, "medium": 50, "large": 120}
FLEET_SIZES = [1, 3, 5, 10, 20]
OPPONENT_COUNTS = [1, 2, 4, 5]

# Performs a full scenario run of the given size_class (number of trades) and seed
def run(idx, size_class, rng):
    trades = TRADE_COUNTS[size_class]
    my_size = rng.choice(FLEET_SIZES)
    n_opp = rng.choice(OPPONENT_COUNTS)
    opp_classes = [rng.choice(OPPONENT_POOL) for _ in range(n_opp)]
    opp_sizes = [rng.choice(FLEET_SIZES) for _ in range(n_opp)]

    out_dir = os.path.join("test_outputs", f"{size_class}_{idx:03d}")
    os.makedirs(out_dir, exist_ok=True)
    
    spec = environment.get_specification_builder(
        environment_files_path=".",
        trades_per_occurrence=trades,
        num_auctions=12,
    )
    spec.add_company(Company19.Data(Company19, make_fleet(my_size, rng), "Company 19"))
    
    for i, (cls, size) in enumerate(zip(opp_classes, opp_sizes)):
        spec.add_company(cls.Data(cls, make_fleet(size, rng), f"{cls.__name__} {i}"))

    sim = environment.generate_simulation(spec, output_directory=out_dir)
    sim.run()
    write_overview(out_dir)

    return {
        "run": out_dir, "size_class": size_class, "trades": trades,
        "my_fleet": my_size, "n_opponents": n_opp,
        "opponents": ";".join(f"{c.__name__}({s})" for c, s in zip(opp_classes, opp_sizes)),
    }

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

# Builds a random fleet of roughly 'size' vessels
def make_fleet(size, rng):
    fleet = []
    while len(fleet) < size:
        fleet += rng.choice(BASE_FLEETS)()
    return fleet[:size]

# Runs 15 scenarios (5 for each size_class/num of trades)
# Generates a random seed instead of running every single possible combination
# This seed can be used to test exact same scenarios with other models
if __name__ == "__main__":
    rng = random.Random(1234) # Generates a random seed
    rows = []
    for size_class in TRADE_COUNTS:
        for idx in range(5):
            try:
                rows.append(run(idx, size_class, rng))
            except Exception as e:
                rows.append({"run": f"{size_class}_{idx:03d}", "size_class" : size_class, "error": repr(e)})

        # Outputs a CSV file of the scenarios
        keys = sorted({k for r in rows for k in r})
        with open("test_outputs/scenarios.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(r for r in rows if r)