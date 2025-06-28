import abc
from pydantic import BaseModel, Field


class Plugin(BaseModel, abc.ABC):
    """Base class for custom scheduled plugins with built-in schedule settings."""

    # scheduling type: 'interval' (every N seconds) or 'daily' (once a day at given time)
    schedule_type: str = Field(
        "interval",
        description="Schedule type: 'interval' or 'daily'",
    )
    # interval seconds for 'interval' scheduling (fallback to PLUGIN_INTERVAL env var if None)
    schedule_interval: int | None = Field(
        None,
        description="Seconds between runs when schedule_type='interval'",
    )
    # time string HH:MM for 'daily' scheduling
    schedule_time: str | None = Field(
        None,
        description="Time of day (HH:MM) when schedule_type='daily'",
    )

    # allow arbitrary types (e.g. SQLAlchemy Session) in BaseModel
    model_config = {"arbitrary_types_allowed": True}

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return plugin name identifier."""
        ...

    @abc.abstractmethod
    def run(self, session) -> None:
        """Execute plugin logic. Receives a DB session."""
        ...