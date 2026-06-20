import pytest

import nroute.core.config
from nroute.core.config import NRouteConfig
from nroute.routing import get_router
from nroute.routing.dijkstra import DijkstraRouter
from nroute.utils.logging import configure_logging


def test_get_router_logs_exception_on_invalid_custom_router(monkeypatch, caplog):
    """Verify that get_router logs an exception when a custom router fails to load."""
    configure_logging()
    # Mock config with an invalid custom router import string
    cfg = NRouteConfig()
    cfg.custom_routers["invalid-router"] = "nonexistent.module:NonexistentClass"

    # Monkeypatch load_config to return our mocked config
    monkeypatch.setattr(nroute.core.config, "load_config", lambda *args, **kwargs: cfg)

    # Calling get_router with an invalid custom router algorithm name.
    # It should log the failure and then raise ValueError because "invalid-router"
    # is not a known built-in algorithm.
    with pytest.raises(ValueError, match="Unknown router name"):
        get_router("invalid-router")

    assert "Failed to load custom router from configuration" in caplog.text
    assert "invalid-router" in caplog.text


def test_get_router_fallback_after_failed_custom_load(monkeypatch, caplog):
    """Verify that get_router falls back to default if custom router load fails."""
    configure_logging()
    # Mock config where "dijkstra" is redefined but invalid
    cfg = NRouteConfig()
    cfg.custom_routers["dijkstra"] = "invalid.module:InvalidClass"

    monkeypatch.setattr(nroute.core.config, "load_config", lambda *args, **kwargs: cfg)

    # Should log error and then return the default DijkstraRouter
    router = get_router("dijkstra")

    assert isinstance(router, DijkstraRouter)
    assert "Failed to load custom router from configuration" in caplog.text
