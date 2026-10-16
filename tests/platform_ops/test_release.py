"""Release manifest determinism, immutability, and rollback (06A local proof)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("release", Path(__file__).parents[2] / "scripts" / "release.py")
release = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(release)


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "config" / "policies").mkdir(parents=True)
    (r / "config" / "policies" / "default.yaml").write_text("a: 1\n")
    (r / "uv.lock").write_text("lock\n")
    (r / "app.py").write_text("print('v1')\n")
    _git(r.parent, "init", "-q", str(r))
    _git(r, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    _git(r, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "v1")
    return r


def _commit(repo, text):
    (repo / "app.py").write_text(text)
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", text)


def test_manifest_is_deterministic_and_hashes_inputs(repo):
    a, b = release.build_manifest(repo), release.build_manifest(repo)
    assert a["manifest_sha256"] == b["manifest_sha256"]
    assert a["input_sha256"]["policy"] and a["input_sha256"]["dependencies"]
    assert a["input_sha256"]["calibration"] is None   # absent inputs are explicit, not guessed


def test_dirty_tree_is_refused(repo):
    (repo / "app.py").write_text("uncommitted\n")
    with pytest.raises(release.ReleaseError, match="commit"):
        release.build_manifest(repo)


def test_untracked_tree_is_refused(repo):
    (repo / "new_module.py").write_text("print('not in archive')\n")
    with pytest.raises(release.ReleaseError, match="commit"):
        release.build_manifest(repo)


def test_build_activate_rollback(repo, tmp_path):
    root = tmp_path / "runtime"
    r1 = release.build(repo, root)
    sha1 = release.activate(root, r1.name)
    _commit(repo, "print('v2')\n")
    r2 = release.build(repo, root)
    sha2 = release.activate(root, r2.name)
    assert sha1 != sha2 and (root / "current" / "DEPLOYED_SHA").read_text().strip() == sha2
    assert release.rollback(root) == sha1
    assert (root / "current" / "app.py").read_text() == "print('v1')\n"
    assert (root / "current" / "DEPLOYED_SHA").read_text().strip() == sha1


def test_tampered_release_fails_verification_and_is_skipped_by_rollback(repo, tmp_path):
    root = tmp_path / "runtime"
    r1 = release.build(repo, root)
    release.activate(root, r1.name)
    _commit(repo, "print('v2')\n")
    r2 = release.build(repo, root)
    release.activate(root, r2.name)
    target = r1 / "app.py"
    target.chmod(0o644)
    target.write_text("tampered\n")
    with pytest.raises(release.ReleaseError, match="checksum"):
        release.verify(r1)
    with pytest.raises(release.ReleaseError, match="no earlier verified release"):
        release.rollback(root)
    assert release.current(root) == r2.name


def test_release_with_an_injected_file_fails_verification(repo, tmp_path):
    built = release.build(repo, tmp_path / "runtime")
    injected = built / "injected.py"
    injected.write_text("unexpected\n")
    with pytest.raises(release.ReleaseError, match="unexpected files"):
        release.verify(built)


def test_release_files_are_read_only(repo, tmp_path):
    r1 = release.build(repo, tmp_path / "runtime")
    assert not (r1 / "app.py").stat().st_mode & 0o222
