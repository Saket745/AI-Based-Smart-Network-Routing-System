"""Routing query models to encapsulate path request parameters."""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RoutingQuery(BaseModel):
    """
    Encapsulates parameters for a routing request.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: str = Field(..., description="Source node ID")
    destination: str = Field(..., description="Destination node ID")
    weight: str | Callable[[dict[str, Any]], float] | None = Field(
        default=None, description="Routing metric (attribute name or weight function)"
    )
    flow_key: str | int | None = Field(
        default=None, description="Key for deterministic path selection (e.g. for ECMP)"
    )
