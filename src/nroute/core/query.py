"""Parameter Object for routing queries."""

from __future__ import annotations

from collections.abc import Callable  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RoutingQuery(BaseModel):
    """
    Encapsulates parameters for a routing request to reduce function signature complexity.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: str = Field(..., description="Source node ID")
    destination: str = Field(..., description="Destination node ID")
    weight: str | Callable[[dict[str, Any]], float] | None = Field(
        default=None, description="Edge attribute name or weight function"
    )
    flow_key: Any = Field(default=None, description="Key for deterministic path selection (ECMP)")
    k: int | None = Field(default=None, description="Number of paths for K-shortest-paths")
