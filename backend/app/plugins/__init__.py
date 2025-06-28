# Plugin system for custom scheduled tasks
"""
Plugin system for custom scheduled tasks. Individual plugins should be listed in __all__.
"""
from .base import Plugin  # noqa: F401
from .daily_summary import plugin as daily_summary  # default daily summary plugin

__all__ = [
    "daily_summary",
]