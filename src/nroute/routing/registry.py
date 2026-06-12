"""Registry for dynamically registering custom third-party routing algorithms."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from nroute.routing.base import BaseRouter

# Dictionary mapping algorithm string names to Router classes
ROUTER_REGISTRY: dict[str, type[BaseRouter]] = {}


def register_router(name: str) -> Callable[[type[BaseRouter]], type[BaseRouter]]:
    """
    Decorator to dynamically register a custom router class.

    Args:
        name: String identifier for the router (e.g. 'my-custom-router').
    """

    def decorator(cls: type[BaseRouter]) -> type[BaseRouter]:
        ROUTER_REGISTRY[name.lower().strip()] = cls
        return cls

    return decorator
