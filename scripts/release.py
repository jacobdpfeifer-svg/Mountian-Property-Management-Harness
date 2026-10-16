#!/usr/bin/env python3
"""Immutable release manifest, local runtime build, activation, and rollback.

    release.py manifest [--repo .]                 print the manifest for HEAD
    release.py build    --root DIR [--repo .]      export HEAD into DIR/releases/<sha12>
    release.py activate --root DIR --release SHA12 point DIR/current at a verified release
    release.py rollback --root DIR                 re-point to the previous verified release
    release.py verify   --root DIR [--release SHA12]

A release is built only from a clean, committed tree (`git archive`), so the
code that runs is exactly a reviewed commit. The manifest records the source
commit and tree, and sha256 of the policy, calibration, schema, migrations and
dependency lock, plus a checksum of every exported file. Its `manifest_sha256`
covers everything except the creation time, so two clean machines produce the
same value for the same commit.

This is a local proof. Deploying to a managed runtime is BLOCKED on operator
infrastructure; scripts/deploy_runtime.sh remains the existing laptop path.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

HASHED_INPUTS = {
    "policy": ["config/policies"],
    "calibration": ["proving_ground_exam/market/calibration.yaml",
                    "proving_ground_exam/market/calibration_v2.yaml"],
    "schema": ["src/db/schema.sql", "src/memory/schema.sql", "src/ops/schema.sql"],
    "migrations": ["src/db/migrations"],
    "dependencies": ["uv.lock", "pyproject.toml"],
}


class ReleaseError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def _archive(repo: Path, commit: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", commit],
                          check=True, capture_output=True).stdout


def _files_from_archive(blob: bytes) -> dict[str, bytes]:
    out = {}
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        for m in tar.getmembers():
            if m.isfile():
                fh = tar.extractfile(m)
                assert fh is not None
                out[m.name] = fh.read()
    return out


def _group_hash(files: dict[str, bytes], prefixes: list[str]) -> str | None:
    h = hashlib.sha256()
    matched = False
    for name in sorted(files):
        if any(name == p or name.startswith(p.rstrip("/") + "/") for p in prefixes):
            matched = True
            h.update(name.encode() + b"\0" + hashlib.sha256(files[name]).digest())
    return h.hexdigest() if matched else None


def build_manifest(repo: Path, *, allow_dirty: bool = False) -> dict:
    commit = _git(repo, "rev-parse", "HEAD")
    # A release must represent *all* reviewed source bytes.  Checking tracked
    # changes alone is unsafe: an untracked feature can be silently omitted by
    # `git archive` while the manifest wrongly describes the older commit.
    dirty = bool(_git(repo, "status", "--porcelain", "--untracked-files=all"))
    if dirty and not allow_dirty:
        raise ReleaseError("tracked files are modified; commit before building a release")
    files = _files_from_archive(_archive(repo, commit))
    body = {
        "format": "wp-price-release/1",
        "source_commit": commit,
        "source_tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "dirty_worktree_at_build": dirty,
        "input_sha256": {k: _group_hash(files, v) for k, v in HASHED_INPUTS.items()},
        "files": {n: hashlib.sha256(b).hexdigest() for n, b in sorted(files.items())},
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return {**body, "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def _releases(root: Path) -> Path:
    return root / "releases"


def build(repo: Path, root: Path) -> Path:
    manifest = build_manifest(repo)
    dest = _releases(root) / manifest["source_commit"][:12]
    if dest.exists():
        verify(dest)
        return dest
    tmp = dest.with_name(dest.name + ".partial")
    tmp.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(_archive(repo, manifest["source_commit"]))) as tar:
        tar.extractall(tmp, filter="data")
    (tmp / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    (tmp / "DEPLOYED_SHA").write_text(manifest["source_commit"] + "\n")
    for p in tmp.rglob("*"):          # immutable once built
        if p.is_file():
            p.chmod(0o444)
    tmp.rename(dest)
    verify(dest)
    return dest


def verify(release_dir: Path) -> dict:
    manifest = json.loads((release_dir / "RELEASE_MANIFEST.json").read_text())
    for name, digest in manifest["files"].items():
        path = release_dir / name
        if not path.is_file():
            raise ReleaseError(f"{release_dir.name}: missing {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ReleaseError(f"{release_dir.name}: checksum mismatch for {name}")
    if (release_dir / "DEPLOYED_SHA").read_text().strip() != manifest["source_commit"]:
        raise ReleaseError(f"{release_dir.name}: DEPLOYED_SHA does not match manifest")
    # A file added after build could be imported ahead of an expected module.
    # Reject it during release verification rather than checking only the files
    # known when the manifest was produced. Runtime caches belong outside a
    # release directory.
    expected = set(manifest["files"]) | {"RELEASE_MANIFEST.json", "DEPLOYED_SHA"}
    actual = {str(p.relative_to(release_dir)) for p in release_dir.rglob("*") if p.is_file()}
    unexpected = actual - expected
    if unexpected:
        raise ReleaseError(f"{release_dir.name}: unexpected files: {sorted(unexpected)}")
    return manifest


def _history(root: Path) -> list[str]:
    path = root / "activation_history.jsonl"
    if not path.exists():
        return []
    return [json.loads(line)["release"] for line in path.read_text().splitlines() if line.strip()]


def activate(root: Path, release: str, *, action: str = "activate") -> str:
    target = _releases(root) / release
    if not target.is_dir():
        raise ReleaseError(f"no release {release}")
    manifest = verify(target)
    link = root / "current"
    tmp = root / "current.tmp"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    tmp.symlink_to(target.relative_to(root))
    os.replace(tmp, link)
    with open(root / "activation_history.jsonl", "a") as fh:
        fh.write(json.dumps({"release": release, "action": action,
                             "source_commit": manifest["source_commit"],
                             "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")
    return manifest["source_commit"]


def current(root: Path) -> str | None:
    link = root / "current"
    return Path(os.readlink(link)).name if link.is_symlink() else None


def rollback(root: Path) -> str:
    """Re-point `current` at the most recent earlier release that still verifies."""
    now = current(root)
    for candidate in reversed(_history(root)):
        if candidate == now:
            continue
        try:
            verify(_releases(root) / candidate)
        except (ReleaseError, FileNotFoundError):
            continue
        return activate(root, candidate, action="rollback")
    raise ReleaseError("no earlier verified release to roll back to")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["manifest", "build", "activate", "rollback", "verify"])
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--root", type=Path)
    ap.add_argument("--release")
    ap.add_argument("--allow-dirty", action="store_true", help="manifest only: report a dirty tree")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "manifest":
            m = build_manifest(a.repo, allow_dirty=a.allow_dirty)
            m.pop("files")
            print(json.dumps(m, indent=1, sort_keys=True))
            return 0
        if a.root is None:
            ap.error("--root is required")
        if a.cmd == "build":
            print(build(a.repo, a.root))
        elif a.cmd == "activate":
            print(activate(a.root, a.release))
        elif a.cmd == "rollback":
            print(rollback(a.root))
        else:
            rel = a.release or current(a.root)
            if rel is None:
                ap.error("no --release given and no current release")
            print(json.dumps({"release": rel, "source_commit": verify(_releases(a.root) / rel)["source_commit"]}))
    except (ReleaseError, subprocess.CalledProcessError) as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
