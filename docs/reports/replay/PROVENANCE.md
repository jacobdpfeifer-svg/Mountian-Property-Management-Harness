# Replay artifact provenance

Date: 2026-09-29

`docs/reports/replay/run2/` was regenerated after Improvement 2. The CSV in that folder and the HTML/JSON were not produced by the same process: the audit notes a 19:49 CSV against a later HTML/JSON rewrite. The copies in this tree now share a later timestamp because the folder was copied again. Do not treat them as one untouched run.

`cli_stdout.log` and `cli_stderr.log` in `run2/` are empty (0 bytes). `docs/reports/replay/improvement_2/CHANGES.md` quotes command output that is not in those logs. The quoted output was not recovered. The empty logs were left as they are.

The operator database copy `run2/operator_copy.db` is a local artifact. It is not a source of prices for a new run.
