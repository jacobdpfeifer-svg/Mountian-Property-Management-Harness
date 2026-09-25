#!/usr/bin/env python3
"""Run the three blind-then-reveal property experiments and a final synthesis.

The runner is deliberately an orchestration layer, not a pricing agent.  It starts
each property agent in a disposable copy of the repository, persists a checkpoint
after every successful stage, and refuses to start the final audit until all three
reports have passed the report-integrity gate.

Example:
    python3 scripts/run_testruns.py run --agent-cmd 'codex exec --full-auto -'

The command receives the prompt on stdin.  It may use these placeholders when a
different agent launcher is needed: {workspace}, {prompt}, {property_id}, {report}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def run_agent(template: str, prompt_text: str, *, cwd: Path, log: Path,
              workspace: Path, prompt: Path, property_id: str, report: Path) -> int:
    command = command_for(template, workspace=workspace, prompt=prompt,
                          property_id=property_id, report=report)
    started = utc_now()
    result = subprocess.run(
        command,
        cwd=str(cwd),
        input=prompt_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=os.environ.copy(),
    )
    log.write_text(
        f"started: {started}\nfinished: {utc_now()}\ncommand: {shlex.join(command)}\n"
        f"exit_code: {result.returncode}\n\n{result.stdout}",
        encoding="utf-8",
    )
    return result.returncode


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
        + "or call set_rate; confirm `Guesty write count: 0` in the report.\n"
    )


def report_gate(report: Path, run: PropertyRun) -> dict[str, Any]:
    if not report.exists():
        raise RuntimeError(f"{run.property_id}: expected report was not created: {report}")
    text = report.read_text(encoding="utf-8")
    required = ["## Orchestrator completion", "blind", "hash", "row count",
                "Guesty write count: 0"]
    missing = [term for term in required if term.lower() not in text.lower()]
    if missing:
        raise RuntimeError(f"{run.property_id}: report integrity gate failed; missing {missing}")
    return {"path": str(report), "sha256": sha256(report), "bytes": report.stat().st_size,
            "validated_at": utc_now()}


def run_properties(args: argparse.Namespace, state: dict[str, Any]) -> None:
    template = args.agent_cmd or os.environ.get("TESTRUN_AGENT_CMD")
    if not template:
        raise RuntimeError("set TESTRUN_AGENT_CMD or pass --agent-cmd (prompt is sent on stdin)")
    RUNS.mkdir(parents=True, exist_ok=True)

    for run in PROPERTIES:
        entry = state["properties"].setdefault(run.property_id, {})
        if entry.get("status") == "complete" and not args.rerun:
            print(f"{run.property_id}: already complete; use --rerun to replace it")
            continue

        session = RUNS / run.property_id
        if session.exists() and args.rerun:
            shutil.rmtree(session)
        session.mkdir(parents=True, exist_ok=True)
        workspace = session / "workspace"
        copy_workspace(workspace)
        prompt = session / "prompt.md"
        report_in_workspace = workspace / "docs/reports" / run.report_name
        prompt.write_text(property_prompt(run, workspace, report_in_workspace), encoding="utf-8")
        log = session / "agent.log"
        db_path = Path("/tmp") / f"testrun_{run.property_id}.db"
        entry.update({"status": "running", "started_at": utc_now(), "workspace": str(workspace),
                      "db": str(db_path), "prompt": str(prompt), "log": str(log)})
        save_state(state)
        print(f"{run.property_id}: starting isolated agent session")
        code = run_agent(template, prompt.read_text(encoding="utf-8"), cwd=workspace, log=log,
                         workspace=workspace, prompt=prompt, property_id=run.property_id,
                         report=report_in_workspace)
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
    text = final.read_text(encoding="utf-8")
    required = [
        "## Orchestrator audit completion",
        "Reports fully reviewed",
        "Guesty write count: 0",
        *[run.report_name for run in PROPERTIES],
    ]
    missing = [term for term in required if term.lower() not in text.lower()]
    if missing:
        raise RuntimeError(f"final audit integrity gate failed; missing {missing}")
    state["audit"].update({"status": "complete", "exit_code": 0, "finished_at": utc_now(),
                            "record": str(final), "sha256": sha256(final)})
    save_state(state)
    print(f"final audit complete: {final}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "status"))
    parser.add_argument("--agent-cmd", help="agent launcher template; prompt is also sent on stdin")
    parser.add_argument("--rerun", action="store_true", help="rerun completed property sessions")
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps(load_state(), indent=2))
        return 0
    state = load_state()
    try:
        run_properties(args, state)
        run_audit(args, state)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"testrun stopped safely: {exc}", file=sys.stderr)
        print(f"resume with: python3 {Path(__file__).relative_to(ROOT)} run", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
