# Plugin system for custom scheduled tasks
from .base import Plugin  # noqa: F401
from .daily_summary import plugin as daily_summary  # default daily summary plugin