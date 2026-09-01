"""Collector package — import registers all collectors with the framework."""

from src.signals.collectors import broken as _broken  # noqa: F401
from src.signals.collectors import snotel as _snotel  # noqa: F401
from src.signals.collectors import weather as _weather  # noqa: F401
from src.signals.collectors import enso as _enso  # noqa: F401
from src.signals.collectors import resort as _resort  # noqa: F401
from src.signals.collectors import cdot as _cdot  # noqa: F401
from src.signals.collectors import calendars as _calendars  # noqa: F401
from src.signals.collectors import regulatory as _regulatory  # noqa: F401
from src.signals.collectors import intent as _intent  # noqa: F401
from src.signals.collectors import flight as _flight  # noqa: F401

__all__ = []
