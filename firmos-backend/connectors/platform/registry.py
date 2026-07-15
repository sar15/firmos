"""Fail-closed connector implementation registry."""
from collections.abc import Callable
from connectors.platform.base import Connector


class ConnectorNotRegistered(LookupError): pass


class ConnectorRegistry:
    def __init__(self): self._factories: dict[tuple[str, str], tuple[frozenset[str], Callable[..., Connector]]] = {}

    def register(self, provider: str, version: str, capabilities: set[str], factory: Callable[..., Connector]) -> None:
        key = (provider.upper(), version)
        if key in self._factories: raise ValueError(f"Connector already registered: {key}")
        self._factories[key] = (frozenset(capabilities), factory)

    def create(self, provider: str, version: str, capability: str, **kwargs) -> Connector:
        registered = self._factories.get((provider.upper(), version))
        if not registered or capability not in registered[0]:
            raise ConnectorNotRegistered(f"No certified implementation for {provider}:{version}:{capability}")
        return registered[1](**kwargs)


registry = ConnectorRegistry()
