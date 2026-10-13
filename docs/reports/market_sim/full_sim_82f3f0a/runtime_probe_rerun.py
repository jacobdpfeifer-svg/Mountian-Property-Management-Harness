# Full-season normal seed 1 engine, full vs incremental, run_market_job defaults (recommendations persisted).
# Usage from the repo root: PYTHONPATH=. .venv/bin/python <this file> <empty output dir>
# Run at 82f3f0a on 2026-10-12, before the guardrail-count fix. Output: runtime_probe_rerun.txt
import sys, time, json
from pathlib import Path
from multiprocessing import Pool
from src.proving_ground.market_loop import run_market_job
out = Path(sys.argv[1])
def job(inc):
    t = time.time()
    r = run_market_job("normal", 1, "engine", db_path=out / f"full_i{int(inc)}.db", incremental=inc)
    return inc, time.time() - t, r.scores, r.content_hash
if __name__ == "__main__":
    with Pool(2) as p:
        res = dict((i, (s, sc, h)) for i, s, sc, h in p.map(job, [False, True]))
    for inc, (s, sc, h) in res.items():
        print(f"inc={inc} {s:.1f}s rev={sc['revenue']} guard={sc['guardrail_triggers']} by={sc['guardrail_by_action']} hash={h}")
    a, b = res[False][1], res[True][1]
    print("hash_match", res[False][2] == res[True][2])
    print("differing", json.dumps({k: (a[k], b[k]) for k in a if a[k] != b[k]}, default=str))
