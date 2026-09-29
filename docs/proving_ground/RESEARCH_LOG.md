# Proving Ground — Research Log (Phase R)

Five sources per track minimum. Verdicts: **clone** / **borrow** / **reject**.

## Track A — Simulation frameworks
| Source | Verdict | Notes |
|--------|---------|-------|
| PassengerSim | reject | Core not public |
| airsim/tvlsim (GPL-3) | borrow | Discrete-event patterns only |
| ABIDES | borrow | Agent kernel + gym wrapper ideas |
| Open Bandit Pipeline | borrow | Off-policy evaluation for baselines |
| skforecast | borrow | Walk-forward validation |
| Mesa | borrow | Lighter ABM than ABIDES |

## Track B — Point-in-time data
| Source | Verdict | License |
|--------|---------|---------|
| NRCS AWDB REST | borrow | Public domain |
| NOAA CPC ONI | borrow | Public domain |
| Open-Meteo historical forecast | borrow/internal | Non-commercial tier — internal_only until licensed |
| IEM NWS archive | borrow | Public |
| BTS T-100 | borrow | Public |

## Track C — Testing
| Source | Verdict |
|--------|---------|
| Hypothesis | borrow |
| mutmut | borrow |
| VCR.py | borrow |
| pandera | borrow |
| Giskard metamorphic | borrow |

## Track D — Evidence presentation
| Source | Verdict |
|--------|---------|
| SR 11-7 | borrow (Evidence Pack skeleton) |
| Backtest bias taxonomies | borrow |
| Model cards | borrow |

## Track E — Independent evaluation loops
| Source | Verdict |
|--------|---------|
| Darwin Gödel Machine | borrow (engine archive) |
| OpenEvolve | borrow (separate evaluator pool) |
| Voyager | borrow (curriculum + playbook) |
| LLM-as-judge bias papers | borrow (cross-model auditors) |
