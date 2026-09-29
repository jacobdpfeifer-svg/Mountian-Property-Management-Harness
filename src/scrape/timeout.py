"""Bound a provider call so a hung HTTP client cannot leave scrape status=running."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable, TypeVar

T = TypeVar("T")


def call_with_timeout(fn: Callable[..., T], timeout_s: float, *args, **kwargs) -> T:
    if timeout_s <= 0:
        return fn(*args, **kwargs)
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(fn, *args, **kwargs)
        return future.result(timeout=timeout_s)
    except FuturesTimeout as exc:
        raise TimeoutError(f"{fn.__name__} exceeded {timeout_s:.0f}s") from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
