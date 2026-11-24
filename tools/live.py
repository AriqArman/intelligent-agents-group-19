"""
Live dashboard while you build: runs your agent and shows the results in the browser.

Usage (from the repo folder):   python tools/live.py
Then open http://127.0.0.1:8019 (it opens by itself).

- "Run" runs run_mine.py (your my_agent.py) and shows your print()s as they happen.
- Tick "Re-run on save" and every time you save my_agent.py it runs again.
- Errors (including ones MABLE hides inside receive) appear in a red box.
- Results come from the newest metrics_competition_*.json, so run_local.py runs show up too.
Standard library only: no extra packages.
"""
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "tools", "live.html")
AGENT = os.path.join(ROOT, "my_agent.py")
PORT = 8019
SCRIPTS = {"run_mine.py", "run_local.py"}
LOGLINE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+ \| (\w+)")
ANSI = re.compile(r"\x1b\[[0-9;]*m")

lock = threading.Lock()
state = {"running": False, "script": None, "started": None, "seconds": None, "exit": None,
         "output": [], "problems": [], "auto": False, "runs": 0}
cache = {}  # path -> (mtime, summary)


def run(script):
    with lock:
        if state["running"]:
            return
        state.update(running=True, script=script, started=time.time(), seconds=None, exit=None,
                     output=[], problems=[])
    proc = subprocess.Popen([sys.executable, "-u", script], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

    def read_out():
        for line in proc.stdout:
            with lock:
                state["output"].append(line.rstrip())
                del state["output"][:-500]

    def read_err():
        level = None  # level of the last log line; follow-on lines (wrapped text, tracebacks) share it
        for line in proc.stderr:
            line = ANSI.sub("", line).rstrip()
            m = LOGLINE.match(line)
            if m:
                level = m.group(1)
            elif line.startswith("Traceback"):
                level = "ERROR"
            # keep crashes and MABLE warnings/errors; drop DEBUG/INFO chatter
            if m and "cargo_distributions" in line:
                level = "NOISE"  # MABLE's own harmless "port not in network, resampling" warnings
            if line and (level is None or level in ("WARNING", "ERROR", "CRITICAL")):
                with lock:
                    if len(state["problems"]) < 300:
                        state["problems"].append(line)

    readers = [threading.Thread(target=read_out), threading.Thread(target=read_err)]
    for t in readers:
        t.start()
    code = proc.wait()
    for t in readers:
        t.join()
    with lock:
        state.update(running=False, exit=code, seconds=round(time.time() - state["started"], 1))
        state["runs"] += 1


def watch_agent():
    last = os.path.getmtime(AGENT) if os.path.exists(AGENT) else None
    while True:
        time.sleep(1)
        now = os.path.getmtime(AGENT) if os.path.exists(AGENT) else None
        if now != last:
            last = now
            if state["auto"] and not state["running"]:
                threading.Thread(target=run, args=("run_mine.py",), daemon=True).start()


def port_name(port):
    return port["name"].rsplit("-", 1)[0]


def summarise(path):
    mtime = os.path.getmtime(path)
    if path in cache and cache[path][0] == mtime:
        return cache[path][1]
    with open(path) as f:
        m = json.load(f)
    names = m["company_names"]
    outcomes = m["global_metrics"]["auction_outcomes"]
    ours = next((k for k, n in names.items() if n.startswith("Group 19")), next(iter(names)))
    companies = []
    for key, name in names.items():
        won = [c for month in outcomes for c in month.get(key, [])]
        cost = m["company_metrics"].get(key, {}).get("fuel_cost", 0)
        revenue = sum(c["payment"] for c in won)
        penalty = m["global_metrics"]["penalty"].get(key, 0)
        companies.append({"key": key, "name": name, "ours": key == ours, "cost": cost,
                          "revenue": revenue, "penalty": penalty, "income": revenue - cost - penalty,
                          "won": len(won), "delivered": sum(1 for c in won if c["fulfilled"])})
    months = [{k: {"won": len(v), "paid": sum(c["payment"] for c in v)} for k, v in month.items()}
              for month in outcomes]
    trades = [{"month": i + 1, "from": port_name(c["trade"]["origin_port"]),
               "to": port_name(c["trade"]["destination_port"]), "amount": c["trade"]["amount"],
               "payment": c["payment"], "delivered": c["fulfilled"]}
              for i, month in enumerate(outcomes) for c in month.get(ours, [])]
    summary = {"file": os.path.basename(path), "time": mtime, "companies": companies,
               "months": months, "trades": trades}
    cache[path] = (mtime, summary)
    return summary


def snapshot():
    files = sorted(glob.glob(os.path.join(ROOT, "metrics_competition_*.json")), key=os.path.getmtime)
    history = []
    for path in files[-20:]:
        try:
            s = summarise(path)
        except Exception:  # half-written or odd file: skip
            continue
        us = next(c for c in s["companies"] if c["ours"])
        rivals = [c["income"] for c in s["companies"] if not c["ours"]]
        history.append({"file": s["file"], "time": s["time"], "name": us["name"],
                        "income": us["income"], "penalty": us["penalty"],
                        "best_rival": max(rivals) if rivals else None})
    latest = None
    for path in reversed(files):
        try:
            latest = summarise(path)
            break
        except Exception:
            continue
    with lock:
        live = dict(state, output=list(state["output"]), problems=list(state["problems"]))
    live["agent_exists"] = os.path.exists(AGENT)
    live["elapsed"] = round(time.time() - live["started"], 1) if live["running"] else None
    return {"live": live, "latest": latest, "history": history}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal quiet
        pass

    def send(self, body, kind="application/json", code=200):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(PAGE, "rb") as f:
                self.send(f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self.send(json.dumps(snapshot()))
        else:
            self.send("{}", code=404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/run" and body.get("script") in SCRIPTS:
            threading.Thread(target=run, args=(body["script"],), daemon=True).start()
            self.send('{"ok": true}')
        elif self.path == "/api/auto":
            state["auto"] = bool(body.get("on"))
            self.send('{"ok": true}')
        else:
            self.send('{"ok": false}', code=400)


if __name__ == "__main__":
    threading.Thread(target=watch_agent, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Live dashboard on {url}  (Ctrl+C to stop)")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    server.serve_forever()
