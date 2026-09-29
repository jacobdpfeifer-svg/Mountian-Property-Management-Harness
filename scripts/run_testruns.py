#!/usr/bin/env python3
"""Run the three blind-then-reveal property experiments and a final synthesis.

The runner is deliberately an orchestration layer, not a pricing agent.  It starts
each property agent in a disposable copy of the repository, persists a checkpoint
after every successful stage, and refuses to start the final audit until all three
reports have passed the report-integrity gate.

Example:
    python3 scripts/run_testruns.py run --agent-cmd 'codex exec --dangerously-bypass-approvals-and-sandbox -'

`--full-auto` is rejected on Codex CLI 0.154+. Resume with `python3 scripts/run_testruns.py run`.
Replace one property with `--rerun-property <id>`. Repair stale `running` rows with
`python3 scripts/run_testruns.py repair-stale`. After reports exist,
`python3 scripts/run_testruns.py seal`.

Watchdogs: TESTRUN_PROPERTY_TIMEOUT_S (default 14400), TESTRUN_IDLE_TIMEOUT_S
(default 1800), TESTRUN_SIGKILL_GRACE_S (default 30).

The command receives the prompt on stdin.  Placeholders: {workspace}, {prompt},
{property_id}, {report}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CURRENT_LAUNCHER = "codex exec --dangerously-bypass-approvals-and-sandbox -"
_ACTIVE: dict[str, Any] = {"state": None, "property_id": None, "proc": None}


def _timeout_s(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    return float(raw)


def check_agent_cmd(template: str, *, allow_legacy: bool = False) -> None:
    if "--full-auto" in template and not allow_legacy:
        raise RuntimeError(
            "launcher uses removed Codex flag --full-auto. "
            f"Use: {CURRENT_LAUNCHER}  (or set TESTRUN_ALLOW_LEGACY_LAUNCHER=1)"
        )
    parts = shlex.split(template)
    exe = parts[0] if parts else ""
    if exe in {"codex", "cursor"} or Path(exe).name in {"codex", "cursor"}:
        found = shutil.which(exe) or Path(exe).exists()
        if not found:
            raise RuntimeError(f"agent executable not on PATH: {exe}")


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["TESTRUN_SKIP_VENV_CREATE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    return env


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".testrun_runs"
STATE_FILE = RUNS / "state.json"


@dataclass(frozen=True)
class PropertyRun:
    property_id: str
    prompt_rel: str
    report_name: str


PROPERTIES = (
    PropertyRun("summit_haus", "docs/testrun/TESTRUN_312_northwoods.md", "TESTRUN_312_northwoods.md"),
    PropertyRun("overlook_ridge", "docs/testrun/TESTRUN_300_northwoods.md", "TESTRUN_300_northwoods.md"),
    PropertyRun("cloud_9", "docs/testrun/TESTRUN_cloud9.md", "TESTRUN_cloud9.md"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_state(state: dict[str, Any]) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(STATE_FILE)


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"version": 1, "created_at": utc_now(), "properties": {}, "audit": {}}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def copy_workspace(destination: Path) -> None:
    """Make an isolated source tree without copying VCS or prior runner state."""
    ignore = shutil.ignore_patterns(
        ".git",
        ".testrun_runs",
        ".venv",
        ".coverage*",
        ".mypy_cache",
        ".pytest_cache",
        "__pycache__",
        "*.egg-info",
        "*.log",
        "*.pyc",
        ".venv",
    )
    shutil.copytree(ROOT, destination, ignore=ignore, dirs_exist_ok=False)


def command_for(template: str, *, workspace: Path, prompt: Path, property_id: str, report: Path) -> list[str]:
    values = {
        "workspace": str(workspace),
        "prompt": str(prompt),
        "property_id": property_id,
        "report": str(report),
    }
    return [part.format(**values) for part in shlex.split(template)]


def _terminate_process(proc: subprocess.Popen[str], grace_s: float) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    deadline = time.time() + grace_s
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.2)
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


def run_agent(template: str, prompt_text: str, *, cwd: Path, log: Path,
              workspace: Path, prompt: Path, property_id: str, report: Path,
              watch_paths: list[Path] | None = None) -> int:
    command = command_for(template, workspace=workspace, prompt=prompt,
                          property_id=property_id, report=report)
    started = utc_now()
    wall_s = _timeout_s("TESTRUN_PROPERTY_TIMEOUT_S", 14400)
    idle_s = _timeout_s("TESTRUN_IDLE_TIMEOUT_S", 1800)
    grace_s = _timeout_s("TESTRUN_SIGKILL_GRACE_S", 30)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        handle.write(f"started: {started}\ncommand: {shlex.join(command)}\n\n")
        handle.flush()
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=child_env(),
        )
        _ACTIVE["proc"] = proc
        assert proc.stdin is not None
        proc.stdin.write(prompt_text)
        proc.stdin.close()
        last_activity = time.time()
        last_sizes = {str(p): p.stat().st_mtime if p.exists() else 0.0 for p in (watch_paths or [])}
        last_log_size = log.stat().st_size
        t0 = time.time()
        timed_out = False
        while proc.poll() is None:
            now = time.time()
            if now - t0 > wall_s:
                handle.write(f"\n[watchdog] wall-clock timeout {wall_s:.0f}s\n")
                handle.flush()
                _terminate_process(proc, grace_s)
                timed_out = True
                break
            moved = False
            for path in watch_paths or []:
                mtime = path.stat().st_mtime if path.exists() else 0.0
                key = str(path)
                if mtime > last_sizes.get(key, 0):
                    last_sizes[key] = mtime
                    moved = True
            size = log.stat().st_size
            if moved or size > last_log_size:
                last_activity = now
                last_log_size = size
            if now - last_activity > idle_s:
                handle.write(f"\n[watchdog] idle timeout {idle_s:.0f}s (no log/file activity)\n")
                handle.flush()
                _terminate_process(proc, grace_s)
                timed_out = True
                break
            time.sleep(1.0)
        code = proc.wait()
        handle.write(f"\nfinished: {utc_now()}\nexit_code: {code}\n")
        if timed_out and code == 0:
            code = 124
        handle.flush()
    _ACTIVE["proc"] = None
    return code


def write_fallback_report(
    report: Path,
    run: PropertyRun,
    *,
    db_path: Path,
    export_path: Path | None,
    reason: str,
) -> None:
    recs = 0
    db_note = "missing"
    if db_path.exists():
        db_note = str(db_path)
        try:
            con = sqlite3.connect(str(db_path))
            recs = int(con.execute(
                "SELECT COUNT(*) FROM price_recommendations WHERE property_id = ?",
                (run.property_id,),
            ).fetchone()[0])
            con.close()
        except sqlite3.Error as exc:
            db_note += f" (unreadable: {exc})"
    export_hash = sha256(export_path) if export_path and export_path.exists() else "n/a"
    export_rows = 0
    if export_path and export_path.exists():
        export_rows = max(0, len(export_path.read_text(encoding="utf-8").splitlines()) - 1)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        f"# {run.report_name} (machine-generated fallback)\n\n"
        f"Status: `failed_report_missing`\n\n"
        f"The child agent did not write this report. {reason}\n\n"
        f"## 1. Executive verdict\n\nMachine fallback. Not a human diagnostic.\n\n"
        f"## Orchestrator completion\n\n"
        f"- DB path: `{db_note}`\n"
        f"- Blind export: `{export_path or 'n/a'}`\n"
        f"- Export SHA-256 / hash: `{export_hash}`\n"
        f"- Export row count: `{export_rows}`\n"
        f"- Recommendation rows in DB: `{recs}`\n"
        f"- Blind-freeze timestamp: `{utc_now()}`\n"
        f"- Guesty write count: 0\n",
        encoding="utf-8",
    )


def export_short_name(property_id: str) -> str:
    return {
        "summit_haus": "testrun_312.csv",
        "overlook_ridge": "testrun_300.csv",
        "cloud_9": "testrun_cloud9.csv",
    }.get(property_id, f"testrun_{property_id}.csv")


def property_prompt(run: PropertyRun, workspace: Path, report: Path) -> str:
    source = (ROOT / run.prompt_rel).read_text(encoding="utf-8")
    return (
        source
        + "\n\n--- ORCHESTRATOR EXECUTION CONTRACT ---\n"
        + f"This is isolated sequential session for property_id={run.property_id}.\n"
        + f"Workspace: {workspace}\nReport path: {report}\n"
        + "Complete every phase in this prompt. Do not hand work back as a plan. "
        + "Before finishing, write the report at the exact report path and include a "
        + "literal heading `## Orchestrator completion` with the DB path, export hash, "
        + "export row count, blind-freeze timestamp, and confirmation that every report "
        + "section was addressed. If a command fails, classify it in the report and "
        + "continue through all safe remaining phases. Never edit files outside the "
        + "isolated workspace except the report. Guesty is read-only: never push rates "
        + "or call set_rate; confirm `Guesty write count: 0` in the report. "
        + "Do not create a new .venv; inherit the parent environment. "
        + "Before recommend, run `wp-price seed-forward-inventory --property "
        + f"{run.property_id} --source guesty-readonly`. "
        + "Every sync-guesty/recommend/audit/export must pass --property "
        + f"{run.property_id}.\n"
    )


def gate_haystack(text: str) -> str:
    """Lowercase report text with `*` / backticks stripped so **0** and `0` still match.

    Underscores are kept so filenames like TESTRUN_312_northwoods.md survive.
    """
    return re.sub(r"[*`]+", "", text).lower()


def export_row_count_from_report(text: str) -> int | None:
    hay = gate_haystack(text)
    match = re.search(r"export row count:\s*(\d+)", hay)
    if not match:
        match = re.search(r"data row count:\s*(\d+)", hay)
    return int(match.group(1)) if match else None


def report_gate(report: Path, run: PropertyRun) -> dict[str, Any]:
    if not report.exists():
        raise RuntimeError(f"{run.property_id}: expected report was not created: {report}")
    text = report.read_text(encoding="utf-8")
    hay = gate_haystack(text)
    required = ["## orchestrator completion", "blind", "hash", "row count",
                "guesty write count: 0"]
    missing = [term for term in required if term not in hay]
    if missing:
        raise RuntimeError(f"{run.property_id}: report integrity gate failed; missing {missing}")
    rows = export_row_count_from_report(text)
    missing_report = "failed_report_missing" in hay
    return {
        "path": str(report),
        "sha256": sha256(report),
        "bytes": report.stat().st_size,
        "validated_at": utc_now(),
        "export_row_count": rows,
        "empty_export": rows == 0,
        "failed_report_missing": missing_report,
    }


def replace_property_session(args: argparse.Namespace, property_id: str) -> bool:
    if args.rerun:
        return True
    return property_id in (args.rerun_property or [])


def ensure_workspace(session: Path, *, replace: bool) -> Path:
    """Reuse an existing isolated copy on resume; copy only when missing or replaced."""
    workspace = session / "workspace"
    if replace and session.exists():
        shutil.rmtree(session)
    session.mkdir(parents=True, exist_ok=True)
    if not workspace.exists():
        copy_workspace(workspace)
    return workspace


def run_properties(args: argparse.Namespace, state: dict[str, Any]) -> None:
    template = args.agent_cmd or os.environ.get("TESTRUN_AGENT_CMD")
    if not template:
        raise RuntimeError("set TESTRUN_AGENT_CMD or pass --agent-cmd (prompt is sent on stdin)")
    check_agent_cmd(template, allow_legacy=bool(os.environ.get("TESTRUN_ALLOW_LEGACY_LAUNCHER")))
    RUNS.mkdir(parents=True, exist_ok=True)

    def _interrupt(signum: int, _frame: Any) -> None:
        proc = _ACTIVE.get("proc")
        pid = _ACTIVE.get("property_id")
        st = _ACTIVE.get("state")
        if proc is not None:
            _terminate_process(proc, _timeout_s("TESTRUN_SIGKILL_GRACE_S", 30))
        if st and pid:
            entry = st["properties"].setdefault(pid, {})
            if entry.get("status") == "running":
                entry.update({"status": "interrupted", "finished_at": utc_now(),
                              "signal": signal.Signals(signum).name})
                save_state(st)
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _interrupt)
    signal.signal(signal.SIGTERM, _interrupt)

    for run in PROPERTIES:
        entry = state["properties"].setdefault(run.property_id, {})
        replace = replace_property_session(args, run.property_id)
        if entry.get("status") == "complete" and not replace:
            print(f"{run.property_id}: already complete; use --rerun-property {run.property_id} to replace it")
            continue

        session = RUNS / run.property_id
        workspace = ensure_workspace(session, replace=replace)
        prompt = session / "prompt.md"
        report_in_workspace = workspace / "docs/reports" / run.report_name
        prompt.write_text(property_prompt(run, workspace, report_in_workspace), encoding="utf-8")
        log = session / "agent.log"
        db_path = Path("/tmp") / f"testrun_{run.property_id}.db"
        export_path = workspace / "data/exports" / export_short_name(run.property_id)
        entry.update({"status": "running", "started_at": utc_now(), "workspace": str(workspace),
                      "db": str(db_path), "prompt": str(prompt), "log": str(log)})
        save_state(state)
        _ACTIVE.update({"state": state, "property_id": run.property_id})
        print(f"{run.property_id}: starting isolated agent session")
        try:
            code = run_agent(
                template, prompt.read_text(encoding="utf-8"), cwd=workspace, log=log,
                workspace=workspace, prompt=prompt, property_id=run.property_id,
                report=report_in_workspace,
                watch_paths=[report_in_workspace, export_path, db_path, log],
            )
        except KeyboardInterrupt:
            entry.update({"status": "interrupted", "finished_at": utc_now()})
            save_state(state)
            raise
        if not report_in_workspace.exists() and (db_path.exists() or (export_path.exists())):
            write_fallback_report(
                report_in_workspace, run, db_path=db_path, export_path=export_path,
                reason="Agent exited without the markdown report; evidence was present.",
            )
            destination = ROOT / "docs/reports" / run.report_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_in_workspace, destination)
            entry.update({"status": "failed_report_missing", "exit_code": code,
                          "finished_at": utc_now()})
            save_state(state)
            raise RuntimeError(
                f"{run.property_id}: agent did not write the report; "
                f"wrote fallback to {destination}; see {log}"
            )
        if code != 0:
            entry.update({"status": "failed", "exit_code": code, "finished_at": utc_now()})
            save_state(state)
            raise RuntimeError(f"{run.property_id}: agent failed with exit code {code}; see {log}")

        metadata = report_gate(report_in_workspace, run)
        destination = ROOT / "docs/reports" / run.report_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report_in_workspace, destination)
        metadata["main_repo_path"] = str(destination)
        entry.update({"status": "complete", "exit_code": 0, "finished_at": utc_now(),
                      "report": metadata})
        save_state(state)
        print(f"{run.property_id}: report frozen and copied to {destination}")
    _ACTIVE.update({"state": None, "property_id": None})


def audit_prompt(state: dict[str, Any], audit_dir: Path) -> str:
    report_paths = [
        state["properties"][run.property_id]["report"]["main_repo_path"]
        for run in PROPERTIES
    ]
    return f"""You are the final cross-property audit agent. This is a new, separate session.

Read every character of these three completed reports, reviewing every section and every
finding, not merely their executive summaries:
{chr(10).join(f'- {p}' for p in report_paths)}

Also read docs/testrun/README_TESTRUN.md, the repo's production-readiness audit, and the
source/tests relevant to each finding. Research externally where the reports require it.
Reconcile contradictions, distinguish observed facts from hypotheses, and decide what is
actually supported. Then implement the necessary, safe, evidence-backed improvements in
the main repository. Do not implement speculative changes or changes that violate the
blind-run protocol. Add or update tests for every code change. Do not alter the three
completed reports or their frozen evidence. Guesty remains read-only — do not push
rates or call set_rate. Confirm `Guesty write count: 0`.

Write a complete audit record to {audit_dir / 'FINAL_AUDIT.md'} containing: report-by-report
coverage, every finding disposition, researched evidence and links, exact files changed,
tests run and results, rejected proposals with reasons, remaining risks, and a forward
shadow-mode plan. Include the literal heading `## Orchestrator audit completion` and list
each report filename under `Reports fully reviewed`.
"""


def run_audit(args: argparse.Namespace, state: dict[str, Any]) -> None:
    if any(state["properties"].get(run.property_id, {}).get("status") != "complete" for run in PROPERTIES):
        raise RuntimeError("final audit is locked until all three property reports pass")
    template = args.agent_cmd or os.environ.get("TESTRUN_AGENT_CMD")
    if not template:
        raise RuntimeError("set TESTRUN_AGENT_CMD or pass --agent-cmd")
    check_agent_cmd(template, allow_legacy=bool(os.environ.get("TESTRUN_ALLOW_LEGACY_LAUNCHER")))
    audit_dir = RUNS / "final_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    prompt = audit_dir / "prompt.md"
    prompt.write_text(audit_prompt(state, audit_dir), encoding="utf-8")
    log = audit_dir / "agent.log"
    state["audit"].update({"status": "running", "started_at": utc_now(), "prompt": str(prompt),
                            "log": str(log)})
    save_state(state)
    code = run_agent(template, prompt.read_text(encoding="utf-8"), cwd=ROOT, log=log,
                     workspace=ROOT, prompt=prompt, property_id="final_audit",
                     report=audit_dir / "FINAL_AUDIT.md")
    final = audit_dir / "FINAL_AUDIT.md"
    if code != 0 or not final.exists():
        state["audit"].update({"status": "failed", "exit_code": code, "finished_at": utc_now()})
        save_state(state)
        raise RuntimeError(f"final audit failed; see {log}")
    try:
        audit_gate(final)
    except RuntimeError:
        state["audit"].update({"status": "failed", "exit_code": code, "finished_at": utc_now()})
        save_state(state)
        raise
    state["audit"].update({"status": "complete", "exit_code": 0, "finished_at": utc_now(),
                            "record": str(final), "sha256": sha256(final)})
    save_state(state)
    print(f"final audit complete: {final}")


def audit_gate(final: Path) -> None:
    if not final.exists():
        raise RuntimeError(f"final audit record missing: {final}")
    text = final.read_text(encoding="utf-8")
    hay = gate_haystack(text)
    required = [
        "## orchestrator audit completion",
        "reports fully reviewed",
        "guesty write count: 0",
        *[run.report_name.lower() for run in PROPERTIES],
    ]
    missing = [term for term in required if term not in hay]
    if missing:
        raise RuntimeError(f"final audit integrity gate failed; missing {missing}")


def seal_from_disk(state: dict[str, Any]) -> None:
    """Validate on-disk reports/audit and checkpoint them without launching agents."""
    RUNS.mkdir(parents=True, exist_ok=True)
    for run in PROPERTIES:
        destination = ROOT / "docs/reports" / run.report_name
        metadata = report_gate(destination, run)
        metadata["main_repo_path"] = str(destination)
        workspace_report = RUNS / run.property_id / "workspace" / "docs/reports" / run.report_name
        workspace_report.parent.mkdir(parents=True, exist_ok=True)
        if not workspace_report.exists():
            shutil.copy2(destination, workspace_report)
        entry = state["properties"].setdefault(run.property_id, {})
        status = "failed_report_missing" if metadata.get("failed_report_missing") else "complete"
        entry.update({
            "status": status,
            "exit_code": 0 if status == "complete" else 1,
            "finished_at": entry.get("finished_at") or utc_now(),
            "db": entry.get("db") or str(Path("/tmp") / f"testrun_{run.property_id}.db"),
            "workspace": entry.get("workspace") or str(RUNS / run.property_id / "workspace"),
            "report": metadata,
        })
        if metadata.get("failed_report_missing"):
            print(f"{run.property_id}: sealed as failed_report_missing")
        elif metadata.get("empty_export"):
            print(f"{run.property_id}: sealed with empty export (blocker report, not a priced year)")
        else:
            print(f"{run.property_id}: sealed {destination}")
    if any(state["properties"].get(run.property_id, {}).get("status") != "complete" for run in PROPERTIES):
        save_state(state)
        raise RuntimeError("seal stopped: not every property is complete (final audit stays locked)")
    final = RUNS / "final_audit" / "FINAL_AUDIT.md"
    audit_gate(final)
    state.setdefault("audit", {})
    state["audit"].update({
        "status": "complete",
        "exit_code": 0,
        "finished_at": utc_now(),
        "record": str(final),
        "sha256": sha256(final),
    })
    save_state(state)
    print(f"final audit sealed: {final}")


def repair_stale(state: dict[str, Any]) -> None:
    """Mark leftover status=running sessions as interrupted."""
    changed = False
    for pid, entry in state.get("properties", {}).items():
        if entry.get("status") == "running":
            entry["status"] = "interrupted"
            entry["finished_at"] = utc_now()
            entry["repaired"] = True
            print(f"{pid}: running -> interrupted")
            changed = True
    if state.get("audit", {}).get("status") == "running":
        state["audit"]["status"] = "interrupted"
        state["audit"]["finished_at"] = utc_now()
        state["audit"]["repaired"] = True
        print("audit: running -> interrupted")
        changed = True
    if changed:
        save_state(state)
    else:
        print("no stale running sessions")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "status", "seal", "repair-stale"))
    parser.add_argument("--agent-cmd", help="agent launcher template; prompt is sent on stdin")
    parser.add_argument("--rerun", action="store_true",
                        help="replace every completed property session (destructive)")
    parser.add_argument("--rerun-property", action="append", default=[], metavar="PROPERTY_ID",
                        help="replace one property session; may be repeated")
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(load_state(), indent=2))
        return 0
    state = load_state()
    try:
        if args.command == "seal":
            seal_from_disk(state)
            return 0
        if args.command == "repair-stale":
            repair_stale(state)
            return 0
        run_properties(args, state)
        run_audit(args, state)
    except KeyboardInterrupt:
        print("testrun interrupted", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"testrun stopped safely: {exc}", file=sys.stderr)
        print(f"resume with: python3 {Path(__file__).relative_to(ROOT)} run", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
