"""Render requirements only after crossing the serialized JSON boundary."""

from __future__ import annotations

import json
from typing import Any


class RequirementsRenderError(ValueError):
    """Raised when the serialized requirements view cannot be rendered."""


def render_serialized_json(serialized: str, specflow: Any) -> str:
    """Parse, validate, and render a serialized requirements JSON document.

    Accepting only ``str`` is deliberate: callers cannot pass the in-memory Quint
    extraction object directly to the human-readable rendering stage.
    """

    if not isinstance(serialized, str):
        raise RequirementsRenderError("requirements renderer accepts serialized JSON text only")
    try:
        parsed = json.loads(serialized)
    except json.JSONDecodeError as exc:
        raise RequirementsRenderError(f"invalid serialized requirements JSON: {exc}") from exc
    # Repository path closure is checked by quintflow/specflow before this
    # pure rendering boundary.  Rendering remains usable for serialized golden
    # fixtures that intentionally do not describe a live repository.
    catalog = specflow.validate_catalog(parsed, trace_root=None)
    return specflow.render(catalog)
