import abc


class Plugin(abc.ABC):
    """Base class for custom scheduled plugins."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return plugin name identifier."""
        pass

    @abc.abstractmethod
    def run(self, session) -> None:
        """Execute plugin logic. Receives a DB session."""
        pass