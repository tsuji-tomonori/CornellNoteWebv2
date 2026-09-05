"""Lossless, bijective mappings between Quint requirement values and JSON.

The mapping layer deliberately performs no sorting, default elision, or semantic
normalisation.  Quint ``List`` order and empty strings are data, so changing
either at this boundary would make the generated JSON a non-invertible view of
the authoritative value.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class MappingError(ValueError):
    """Raised when a Quint value cannot be mapped without loss."""


CATALOG_FIELDS = {
    "schemaVersion": "schema_version",
    "catalogRevision": "catalog_revision",
    "product": "product",
    "updatedAt": "updated_at",
    "requirements": "requirements",
}
REQUIREMENT_FIELDS = {
    "id": "id",
    "revision": "revision",
    "status": "status",
    "kind": "type",
    "title": "title",
    "subject": "subject",
    "actionName": "action",
    "objectName": "object",
    "rationale": "rationale",
    "sourceRefs": "source_refs",
    "acceptanceCriteria": "acceptance_criteria",
    "verification": "verification",
    "traces": "traces",
    "lastChangedBy": "last_changed_by",
    "retirementReason": "retirement_reason",
    "supersededBy": "superseded_by",
    "scopeName": "scope",
    "categoryName": "category",
}
CRITERION_FIELDS = {
    "id": "id",
    "given": "given",
    "when_": "when",
    "expected": "then",
}
VERIFICATION_FIELDS = {"method": "method", "evidence": "evidence"}
TRACE_FIELDS = {
    "design": "design",
    "implementation": "implementation",
    "tests": "tests",
    "standards": "standards",
}
def _map_exact(value: Any, fields: Mapping[str, str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MappingError(f"{label} must be an object")
    missing = set(fields) - set(value)
    extra = set(value) - set(fields)
    if missing or extra:
        raise MappingError(f"{label} fields drift: missing={sorted(missing)} extra={sorted(extra)}")
    return {target: value[source] for source, target in fields.items()}


def _reverse_fields(fields: Mapping[str, str]) -> dict[str, str]:
    reversed_fields = {target: source for source, target in fields.items()}
    if len(reversed_fields) != len(fields):
        raise MappingError("mapping targets must be unique")
    return reversed_fields


def criterion_to_json(value: Any) -> dict[str, Any]:
    """Map every acceptance-criterion field, including Given/When/Then semantics."""

    return _map_exact(value, CRITERION_FIELDS, "acceptance criterion")


def criterion_from_json(value: Any) -> dict[str, Any]:
    """Invert :func:`criterion_to_json` without changing field values."""

    return _map_exact(value, _reverse_fields(CRITERION_FIELDS), "JSON acceptance criterion")


def requirement_to_json(value: Any) -> dict[str, Any]:
    """Map one Quint Requirement without silently dropping current or future fields."""

    mapped = _map_exact(value, REQUIREMENT_FIELDS, "requirement")
    mapped["acceptance_criteria"] = [criterion_to_json(item) for item in mapped["acceptance_criteria"]]
    mapped["verification"] = _map_exact(mapped["verification"], VERIFICATION_FIELDS, "verification")
    mapped["traces"] = _map_exact(mapped["traces"], TRACE_FIELDS, "traces")
    return mapped


def requirement_from_json(value: Any) -> dict[str, Any]:
    """Invert :func:`requirement_to_json`, including empty lifecycle fields."""

    mapped = _map_exact(value, _reverse_fields(REQUIREMENT_FIELDS), "JSON requirement")
    mapped["acceptanceCriteria"] = [
        criterion_from_json(item) for item in mapped["acceptanceCriteria"]
    ]
    mapped["verification"] = _map_exact(
        mapped["verification"], _reverse_fields(VERIFICATION_FIELDS), "JSON verification"
    )
    mapped["traces"] = _map_exact(
        mapped["traces"], _reverse_fields(TRACE_FIELDS), "JSON traces"
    )
    return mapped


def catalog_to_json(value: Any) -> dict[str, Any]:
    """Map a complete Quint Catalog while preserving its ``List`` order."""

    mapped = _map_exact(value, CATALOG_FIELDS, "catalog")
    mapped["requirements"] = [requirement_to_json(item) for item in mapped["requirements"]]
    return mapped


def catalog_from_json(value: Any) -> dict[str, Any]:
    """Invert :func:`catalog_to_json` exactly."""

    mapped = _map_exact(value, _reverse_fields(CATALOG_FIELDS), "JSON catalog")
    mapped["requirements"] = [
        requirement_from_json(item) for item in mapped["requirements"]
    ]
    return mapped


def assert_bijective_catalog(value: Any) -> dict[str, Any]:
    """Return the JSON view after proving the value round-trips exactly."""

    mapped = catalog_to_json(value)
    restored = catalog_from_json(mapped)
    if restored != value:
        raise MappingError("catalog mapping is not bijective")
    return mapped
