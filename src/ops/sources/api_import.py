"""Run one API source import through the shared write path."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Callable, Iterable

from src.ops import TurnoverOutcome
from src.ops.db import ImportResult, finish_import, record_outcomes, start_import
from src.ops.sources import PropertyResolver, SourceUnconfigured


def _normalize_all(
    items: Iterable[dict[str, Any]],
    normalize: Callable[[dict[str, Any]], TurnoverOutcome | None],
    result: ImportResult,
) -> list[TurnoverOutcome]:
    out: list[TurnoverOutcome] = []
    for item in items:
        try:
            o = normalize(item)
        except (ValueError, KeyError, TypeError) as exc:
            result.rows_in += 1
            result.rejected += 1
            result.errors.append(str(exc))
            continue
        if o is not None:
            out.append(o)
    return out


def import_guesty_tasks(conn: sqlite3.Connection, start: date, end: date,
                        get: Callable[..., Any] | None = None) -> ImportResult:
    from src.ops.sources import guesty_tasks as gt

    result = start_import(conn, gt.SOURCE, "outcomes")
    try:
        getter = get or gt.client_getter()
    except SourceUnconfigured as exc:
        result.errors.append(str(exc))
        return finish_import(conn, result, status="unconfigured")
    resolver = PropertyResolver(conn)
    try:
        outcomes = _normalize_all(gt.fetch_tasks(getter, start, end),
                                  lambda t: gt.normalize_task(t, resolver), result)
    except Exception as exc:  # network / auth / shape: record and fail closed
        result.errors.append(f"{type(exc).__name__}: {exc}")
        return finish_import(conn, result, status="failed")
    record_outcomes(conn, outcomes, result)
    return finish_import(conn, result)


def import_breezeway(conn: sqlite3.Connection, start: date, end: date,
                     get: Callable[..., Any] | None = None) -> ImportResult:
    from src.ops.sources import breezeway as bw

    result = start_import(conn, bw.SOURCE, "outcomes")
    try:
        getter = get or bw.BreezewayClient().get
    except SourceUnconfigured as exc:
        result.errors.append(str(exc))
        return finish_import(conn, result, status="unconfigured")
    resolver = PropertyResolver(conn)
    try:
        home_map = bw.homes(getter, resolver)
        if not home_map:
            result.errors.append("no Breezeway homes matched a Mont Luxe property")
            return finish_import(conn, result, status="failed")
        outcomes = _normalize_all(bw.fetch_tasks(getter, sorted(home_map), start, end),
                                  lambda t: bw.normalize_task(t, home_map, resolver), result)
    except Exception as exc:
        result.errors.append(f"{type(exc).__name__}: {exc}")
        return finish_import(conn, result, status="failed")
    record_outcomes(conn, outcomes, result)
    return finish_import(conn, result)


def import_turno(conn: sqlite3.Connection, start: date, end: date,
                 get: Callable[..., Any] | None = None) -> ImportResult:
    from src.ops.sources import turno

    result = start_import(conn, turno.SOURCE, "outcomes")
    try:
        getter = get or turno.TurnoClient().get
    except SourceUnconfigured as exc:
        result.errors.append(str(exc))
        return finish_import(conn, result, status="unconfigured")
    resolver = PropertyResolver(conn)
    try:
        outcomes = _normalize_all(turno.fetch_projects(getter, start, end),
                                  lambda p: turno.normalize_project(p, resolver), result)
    except Exception as exc:
        result.errors.append(f"{type(exc).__name__}: {exc}")
        return finish_import(conn, result, status="failed")
    record_outcomes(conn, outcomes, result)
    return finish_import(conn, result)
