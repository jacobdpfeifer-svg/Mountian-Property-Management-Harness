"""Deterministic streams. Scenario and seed only — not Python's hash salt."""

from __future__ import annotations

import hashlib

import numpy as np


def seed_int(scenario: str, seed: int, *parts: object) -> int:
    raw = ":".join([scenario, str(seed), *[str(p) for p in parts]]).encode()
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], "little")


def generator(scenario: str, seed: int, *parts: object) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(seed_int(scenario, seed, *parts)))
