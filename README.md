# intelligent-agents-group-19
Intelligent Agents Group 19

Coursework repo for **COMP6203 Intelligent Agents** (University of Southampton, 2026/27): a tramp-trade maritime shipping agent built on the MABLE simulator.

| | |
|---|---|
| Agent file | [`group19.py`](group19.py) |
| Agent class | `Company19` (must inherit `TradingCompany`) |
| Coursework weight | 40% of module |
| Contact | Keniel Peart (k.peart@soton.ac.uk) |

## Contents
- [Overview](#overview)
- [MABLE](#mable)
- [Submission](#submission)
- [Tournament rules](#tournament-rules)
- [Report requirements](#report-requirements)
- [Assessment and tests](#assessment-and-tests)
- [Deadlines](#deadlines)
- [Reading list](#reading-list)

## Overview
Build a software agent that runs a tramp-trade shipping company. Tramp vessels have no fixed schedule and trade on a spot market for immediate delivery. Cargo auctions are held regularly; each company bids the price it would accept to be paid to transport a cargo, then must deliver the contracts it wins.

Deliverables (submitted separately):
1. **Agent**: [`group19.py`](group19.py) containing class `Company19`, inheriting `TradingCompany`. It currently holds the provided template; the example implementation also lets you run your own local tournaments (see Lab 4).
2. **Group report**: research-paper-style analysis of the agent (see [Report requirements](#report-requirements)).

Rules on reuse:
- Ideas from existing work are allowed **if referenced** in the report. A similar tournament ran at AAMAS'25: [competition website](https://jbuerman.github.io/Maritime-Shipping-Competition-AAMAS2025/). Reports from the top teams:
  - 1st: [Fast Scheduling and Robust Pricing](docs/aamas25/1st-place-delft.pdf) (Mai, Ou; TU Delft)
  - 2nd: [Team Oil Spill MABLE Competition Agent](docs/aamas25/2nd-place-oil-spill.pdf) (Gaskins, Brue; University of Tulsa)
  - 3rd: [Optimizing Vessel Scheduling and Trade Bidding with Simulated Annealing](docs/aamas25/3rd-place-simulated-annealing.pdf) (Flavin; University of Tulsa)
- **No code from existing implementations.** Agent must be entirely our own work; code from the labs is allowed.
- Extra Python packages need approval from Keniel Peart so they can be installed on the tournament machine.

## MABLE
MABLE is an agent-based maritime cargo transportation simulator in Python. A setting defines ports, a cargo market with one homogeneous continuous cargo (e.g. oil), and shipping companies. When run, the simulator generates random cargo transport opportunities that companies bid for and then must carry from one port to another.

For the coursework the world (ports, cargo market) is already specified; we only define the shipping company's behaviour.

### Setup
Full instructions: [lab sheet](docs/COMP6203_Lab_Sheet.pdf), Lab 1, section 1.2.3.

1. Python **3.11 or newer** ([download guide](https://wiki.python.org/moin/BeginnersGuide/Download)).
2. `pip install mable` ([PyPI](https://pypi.org/project/mable/)).
   - If that fails, download the wheel `mable-0.0.13.post3-py3-none-any.whl` from [PyPI files](https://pypi.org/project/mable/#files) and run `pip install mable-0.0.13.post3-py3-none-any.whl`.
   - If you get `Field.__init__() got an unexpected keyword argument 'default'`, install the [fixed MABLE wheel](https://sotonac-my.sharepoint.com/:u:/g/personal/jln1g19_soton_ac_uk/EfaYHnHzHXFNni0FZikQ1_wB2mgReW4hHIXFOHbV07WOEw?e=0JIemi) instead (Soton login).
3. Download [`mable_resources.zip`](https://sotonac-my.sharepoint.com/:u:/g/personal/jln1g19_soton_ac_uk/EeNREwaADQZLrfizEUxG-ZQBnGdjNrkJD_jKqKrUCl0M2g?e=7dPFF2) ([alternate](https://github.com/jbuerman/Maritime-Shipping-Competition-AAMAS2025/raw/main/files/mable_resources.zip)) and put it, still zipped, in the working directory.

Docs: [MABLE API](https://mable-doc.netlify.app/) · [default `TradingCompany` implementation](https://mable-doc.netlify.app/tradingagentintroduction#default-implementation) · [source](https://github.com/jbuerman/mable)

### Running
A minimal run with the agent (lab sheet, section 1.3):

```python
from mable.examples import environment, fleets
from group19 import Company19

if __name__ == '__main__':
    specifications_builder = environment.get_specification_builder(environment_files_path=".")
    fleet = fleets.example_fleet_1()
    specifications_builder.add_company(Company19.Data(Company19, fleet, "Group 19"))
    sim = environment.generate_simulation(specifications_builder)
    sim.run()
```

The run writes `metrics_competition_<number>.json`. Summarise income with `mable overview metrics_competition_<number>.json`.

## Submission
Agent and report are submitted separately, via links on the module page. **Submission links are not posted yet.**

- Agent: `group19.py` with class `Company19`.
- Report: PDF, see [Report requirements](#report-requirements).

## Tournament rules
- Each competition: every agent gets a fleet and runs **one year** of shipping operations.
- **12 cargo auctions**, one per month. During any month's auction, information on the **following month's** auction is available.
- Heterogeneous fleets: competitions are repeated so each agent operates each fleet at least once. Fleet sizes vary from small to large, so the agent must be generic across fleet sizes, ship types, cargoes and locations.
- Run sizes:

  | Run | Trades per month |
  |---|---|
  | Small | ≤ 20 |
  | Medium | ≤ 50 |
  | Large | ≤ 140 |

- **Income** = revenue from won contracts − fleet running costs − penalties for unfulfilled contracts.
- In each run agents are ranked on income relative to each other; final results use the **average rank** across all runs.
- Marking per competition: best agent gets the max score, cohort average gets 65%; scaled separately per competition, final mark is the average over all competitions.
- A **preliminary tournament** runs end of November. It does not count toward marks but gives feedback. Run our own tests and benchmarks too.

## Report requirements
- **≤ 2500 words**, excluding abstract, tables, figures, references, contribution statement and appendix. Over-length is penalised.
- **≤ 6 double-column pages** total, including references and appendices. Over the page limit may not be marked.
- Research-paper style, double-column format ([Overleaf two-column templates](https://www.overleaf.com/gallery/tagged/twocolumn)).
- Must include author names, student numbers, group number and word count.

Must describe at minimum:
1. Overall agent design and strategy (scheduling, handling trade and competitor uncertainty, bidding, etc.), with pseudocode where applicable.
2. Reasons behind the design, how it compares to or differs from existing approaches, with references to relevant literature.
3. Evaluation of performance on chosen metrics against benchmarks (e.g. other agents).
4. Critical evaluation and how the agent could be improved.
5. Individual contribution statement (only if contributions were not equal).

Expectations:
- Several graphs and/or tables of results.
- Encouraged to evaluate strategy variants (or specific parts, e.g. scheduling) to motivate final design choices.
- Cite literature to motivate design and to compare and contrast with existing work.
- No need to describe the competition in detail; a brief overview is fine.
- See the coursework specification for the indicative marking scheme.

## Assessment and tests
| Component | Weight |
|---|---|
| Coursework (agent + report) | 40% |
| 3 tests (equal weight) | 10% total |
| Final exam | 50% |

Tests are timed online multiple-choice-style quizzes (may include numerical and multiple-select questions), held Tuesdays 14:00–16:00 in weeks 6, 9 and 11, replacing the lab.

| Test | Topics |
|---|---|
| Test 1 | Utility Theory, Strategic-form Games, Auctions, Sequential Auctions |
| Test 2 | Strategic-form Games, Extensive-form Games, Cooperative Games |
| Test 3 | Negotiation, Voting |

## Deadlines
| Week | Date and time | Deliverable |
|---|---|---|
| 3 | 09/10/2026 14:00 | Submit team information |
| 6 | 27/10/2026 14:00 | Test 1 |
| 9 | 17/11/2026 14:00 | Test 2 |
| 10 | 27/11/2026 16:00 | Submit preliminary agent |
| 11 | 01/12/2026 14:00 | Test 3 |
| 12 | 11/12/2026 16:00 | Submit final agent and group report |

## Reading list
Links to online copies are on the COMP6203 reading list.

Recommended:
- M. J. Wooldridge (2009). *An Introduction to MultiAgent Systems*, 2nd ed., Wiley. Accompanying lecture slides also useful.
- Y. Shoham and K. Leyton-Brown. *Multiagent Systems: Algorithmic, Game-Theoretic, and Logical Foundations*. Free; more game-theoretic focus.

Additional:
- M. Maschler, E. Solan and S. Zamir. *Game Theory*. Cambridge University Press. In-depth formal treatment.
- N. Nisan, T. Roughgarden, É. Tardos and V. Vazirani (eds.). *Algorithmic Game Theory*. Advanced; beyond module scope.
