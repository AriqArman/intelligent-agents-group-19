"""
Margin sweep: runs run_local.py for each (margin, trades/auction, fleet size) and tabulates Company19's results.

Usage:  python sweep.py
Metrics files go to runs/; the table is printed and written to runs/sweep.md.
"""
import glob
import json
import os
import subprocess
import sys

MARGINS = [-1, 0.0, 0.1, 0.2, 0.4, 1.0]  # -1 = never bid (idle-cost baseline)
CONFIGS = [(5, 2), (10, 3), (15, 4), (30, 4)]  # (trades per auction, vessels per company)

os.makedirs("runs", exist_ok=True)
rows = ["| trades/auction | vessels | margin | won | revenue | cost | penalty | income | best rival income |",
        "|---|---|---|---|---|---|---|---|---|"]
for trades, vessels in CONFIGS:
    for margin in MARGINS:
        before = set(glob.glob("metrics_competition_*.json"))
        subprocess.run([sys.executable, "run_local.py", str(margin), str(trades), str(vessels)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        (path,) = set(glob.glob("metrics_competition_*.json")) - before
        target = os.path.join("runs", f"t{trades}_v{vessels}_m{margin}.json")
        os.replace(path, target)
        data = json.load(open(target))
        outcomes = data["global_metrics"]["auction_outcomes"]
        result = {}
        for cid in data["company_names"]:
            revenue = sum(c["payment"] for a in outcomes for c in a.get(cid, []))
            cost = data["company_metrics"][cid]["fuel_cost"]
            penalty = data["global_metrics"]["penalty"].get(cid, 0)
            won = sum(len(a.get(cid, [])) for a in outcomes)
            result[cid] = (won, revenue, cost, penalty, revenue - cost - penalty)
        won, revenue, cost, penalty, income = result["0"]
        rival = max(r[4] for cid, r in result.items() if cid != "0")
        rows.append(f"| {trades} | {vessels} | {margin} | {won} | {revenue:.0f} | {cost:.0f} | "
                    f"{penalty:.0f} | {income:.0f} | {rival:.0f} |")
        print(rows[-1], flush=True)

with open(os.path.join("runs", "sweep.md"), "w") as f:
    f.write("\n".join(rows) + "\n")
