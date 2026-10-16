"""Runtime environment identity and read/write credential separation.

`WP_PRICE_ENV` names the environment: demo, simulation, staging, or production.
Unset or unrecognised means `unknown`, which may read but can never write.

Credentials are resolved by purpose. Reads use GUESTY_CLIENT_ID/SECRET (the
existing sync credential). Writes use a *separate* GUESTY_WRITE_CLIENT_ID/SECRET
pair and never fall back to the read pair: a host that only holds read
credentials cannot write even if every other gate were open.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from enum import Enum


class Environment(str, Enum):
    DEMO = "demo"
    SIMULATION = "simulation"
    STAGING = "staging"
    PRODUCTION = "production"
    UNKNOWN = "unknown"


class EnvironmentMismatch(RuntimeError):
    """The process environment and the database identity disagree."""


class MissingSecret(RuntimeError):
    """A credential required for the requested purpose is absent."""


ENV_VAR = "WP_PRICE_ENV"


def current_environment() -> Environment:
    raw = (os.environ.get(ENV_VAR) or "").strip().lower()
    try:
        return Environment(raw)
    except ValueError:
        return Environment.UNKNOWN


# Which db_identity.kind values each environment may open for writing state.
_DB_KIND_FOR_ENV = {
    Environment.PRODUCTION: {"production"},
    Environment.STAGING: {"demo", "unknown"},
    Environment.SIMULATION: {"demo", "unknown"},
    Environment.DEMO: {"demo"},
}


def check_db_matches_environment(conn: sqlite3.Connection, env: Environment | None = None) -> None:
    """Refuse a database whose recorded identity does not belong to this environment.

    Production may only open a database marked production, and no non-production
    environment may open a production database.
    """
    from src.db import get_db_identity

    env = env or current_environment()
    kind = get_db_identity(conn).kind
    if env is Environment.UNKNOWN:
        raise EnvironmentMismatch(f"{ENV_VAR} is unset or invalid; refusing to bind to a {kind} database")
    if kind not in _DB_KIND_FOR_ENV[env]:
        raise EnvironmentMismatch(f"environment {env.value} may not use a {kind} database")


class CredentialPurpose(str, Enum):
    READ = "read"
    WRITE = "write"


_VARS = {
    CredentialPurpose.READ: ("GUESTY_CLIENT_ID", "GUESTY_CLIENT_SECRET"),
    CredentialPurpose.WRITE: ("GUESTY_WRITE_CLIENT_ID", "GUESTY_WRITE_CLIENT_SECRET"),
}


@dataclass(frozen=True)
class Credential:
    purpose: CredentialPurpose
    client_id: str
    client_secret: str

    def __repr__(self) -> str:  # never print the secret
        return f"Credential(purpose={self.purpose.value}, client_id=***{self.client_id[-4:]})"

    __str__ = __repr__


def resolve_credential(purpose: CredentialPurpose) -> Credential:
    """Return the credential for `purpose`, or raise MissingSecret. No fallback."""
    id_var, secret_var = _VARS[purpose]
    client_id = (os.environ.get(id_var) or "").strip()
    secret = (os.environ.get(secret_var) or "").strip()
    if not client_id or not secret:
        raise MissingSecret(f"{purpose.value} credential missing ({id_var}/{secret_var})")
    if purpose is CredentialPurpose.WRITE:
        read_id = (os.environ.get(_VARS[CredentialPurpose.READ][0]) or "").strip()
        if read_id and read_id == client_id:
            raise MissingSecret(
                "write credential must be distinct from the read credential; "
                "refusing to treat the sync credential as write authority"
            )
    return Credential(purpose, client_id, secret)
