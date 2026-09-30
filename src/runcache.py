"""Run-scoped memoization for pure, read-only engine lookups.

One `generate_recommendations` call prices ~365 nights, and each night re-derives
the same read-only facts (SQI for a historical stay date, the demand index). The
signal store and demand tables are not written while a run is pricing, so inside a
run those lookups are pure functions of their arguments.

Outside `engine_run_cache()` nothing is cached: tests and callers that mutate the
DB between calls keep today's exact behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")

_ACTIVE: ContextVar[dict[Hashable, Any] | None] = ContextVar("engine_run_cache", default=None)


@contextmanager
def engine_run_cache() -> Iterator[None]:
    """Enable memoization for the duration of one pricing run (re-entrant)."""
    if _ACTIVE.get() is not None:
        yield
        return
    token = _ACTIVE.set({})
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def memo(key: Hashable, compute: Callable[[], T]) -> T:
    """Return the cached value for ``key`` inside a run, else compute it."""
    cache = _ACTIVE.get()
    if cache is None:
        return compute()
    if key in cache:
        return cache[key]
    value = compute()
    cache[key] = value
    return value
