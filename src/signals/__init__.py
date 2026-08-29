"""Pfeifer Optimization — agent-native market intelligence layer.

Agents write typed observations into the Signal Store. Deterministic feature
builders turn observations into pricing inputs. The guarded engine alone
writes prices. LLM agents are confined to schema-bound extraction.
"""

from src.signals.store import SignalStore

__all__ = ["SignalStore"]
