#!/usr/bin/env python3
"""Render Skill contracts and audit the portable repository-policy boundary.

The Quint catalog is authoritative.  This module contains only deterministic
views and mechanical checks which cannot conveniently be expressed in Quint:

* generated contract blocks embedded in ``SKILL.md``;
* content digests which bind a contract to its manual, interface, and assets;
* fail-closed checks that portable assets do not configure repository policy.

The policy checks deliberately cover prose and the four structured formats
currently shipped by portable assets (JSON, YAML, TOML, and Python). They are
not a general-purpose parser or policy engine.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

GENERATED_BLOCK_START = "<!-- BEGIN GENERATED QUINT CONTRACT -->"
GENERATED_BLOCK_END = "<!-- END GENERATED QUINT CONTRACT -->"
_HOST_SPECIFIC_SKILL_PATH = re.compile(r"\.(?:agents|claude)/skills(?:/|\b)")

REPOSITORY_POLICY_FIELDS = (
    "ciWorkflow",
    "requiredCheck",
    "branchProtection",
    "ruleset",
    "mergeStrategy",
    "prTemplate",
    "commitFormat",
)

SKILL_CONTRACT_FIELDS = frozenset(
    {
        "name",
        "role",
        "pillar",
        "guardrail",
        "repositoryBlocking",
        "defaultPortable",
        "repositoryPolicy",
        "applicability",
        "activationContexts",
        "authority",
        "sideEffect",
        "externalEffect",
        "precondition",
        "postcondition",
        "inputs",
        "outputs",
        "obligationIds",
        "prohibitions",
        "requiredAssets",
        "dependencies",
        "failureState",
        "requirementIds",
        "manualBodySha256",
        "payloadSha256",
        "interfaceSha256",
    }
)

_CONTRACT_STRING_FIELDS = frozenset(
    {
        "name",
        "role",
        "pillar",
        "applicability",
        "authority",
        "sideEffect",
        "precondition",
        "postcondition",
        "failureState",
    }
)
_CONTRACT_BOOLEAN_FIELDS = frozenset(
    {"guardrail", "repositoryBlocking", "defaultPortable", "externalEffect"}
)
_CONTRACT_LIST_FIELDS = frozenset(
    {
        "activationContexts",
        "inputs",
        "outputs",
        "obligationIds",
        "prohibitions",
        "requiredAssets",
        "dependencies",
        "requirementIds",
    }
)
_NONEMPTY_CONTRACT_LIST_FIELDS = frozenset(
    {"activationContexts", "inputs", "outputs", "obligationIds", "prohibitions"}
)
_DIGEST_FIELDS = frozenset(
    {"manualBodySha256", "payloadSha256", "interfaceSha256"}
)
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_SKILL_NAME_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")

_ALLOWED_PILLARS = frozenset({"requirements", "design", "checks", "auxiliary"})
_GUARDRAIL_PILLARS = frozenset({"requirements", "design", "checks"})
_ALLOWED_APPLICABILITY = frozenset(
    {
        "when-explicitly-requested",
        "when-concrete-duty-exists",
        "when-external-authority-boundary-exists",
        "when-ambiguity-changes-result",
        "when-development-is-requested",
        "when-frontend-design-is-needed",
        "when-frontend-requirements-are-needed",
        "when-a-declared-generator-supports-the-change",
        "when-frontend-implementation-is-requested",
        "when-change-relevant-checks-exist",
        "when-user-or-target-selects-style",
        "when-durable-obligation-changes-or-authority-is-initialized",
        "when-reference-assets-change",
        "when-evidenced-systemic-trigger-exists",
        "when-execution-sizing-is-needed",
        "when-frontend-testing-is-requested",
        "when-a-relevant-standard-is-selected",
    }
)
_ALLOWED_ACTIVATION_CONTEXTS = frozenset(
    {
        "explicit-review-request",
        "concrete-regulated-duty",
        "external-authority-boundary",
        "material-ambiguity",
        "development-request",
        "frontend-requirements",
        "frontend-design",
        "frontend-implementation",
        "frontend-testing",
        "supported-as-built-surface",
        "selected-checks",
        "target-commit-style",
        "durable-requirement-change",
        "reference-maintenance",
        "evidenced-systemic-failure",
        "execution-sizing",
        "relevant-standard",
    }
)
_ALLOWED_AUTHORITIES = frozenset(
    {
        "artifact-authority",
        "concrete-duty-or-user",
        "explicit-user-authorization",
        "user-intent",
        "user-and-target-repository",
        "approved-requirements",
        "implementation",
        "requirements-and-design",
        "target-repository-and-selected-checks",
        "explicit-user-or-target-repository-style",
        "quint-requirements",
        "reference-repository",
        "observed-defect",
        "change-risk",
        "frontend-requirements-and-approved-design",
        "canonical-requirements-target-policy-and-selected-official-standards",
    }
)
_ALLOWED_SIDE_EFFECTS = frozenset(
    {
        "none",
        "repository-write",
        "repository-and-authorized-external-write",
        "repository-confined-temporary-write",
        "target-command-effects",
    }
)
_ALLOWED_FAILURE_STATES = frozenset(
    {
        "report-bounded",
        "no-op-unless-triggered",
        "no-op-unless-selected",
        "return-for-clarification",
        "return-to-requirements",
        "return-to-design",
        "stop-at-authority-boundary",
        "fail-on-drift",
        "fail-on-invalid-catalog",
    }
)

EXPECTED_SKILL_NAMES = frozenset(
    {
        "adversarial-review",
        "author-lifecycle-docs",
        "authorize-autonomous-execution",
        "calibrated-collaborative-listening",
        "chat-first-development",
        "design-frontend-experience",
        "elicit-frontend-requirements",
        "generate-implementation-design",
        "govern-development-request",
        "implement-frontend-experience",
        "inspect-quality-gates",
        "japanese-git-commit-gitmoji",
        "maintain-canonical-requirements",
        "maintain-reference-repository",
        "retrospect-and-improve",
        "right-size-execution",
        "test-frontend-experience",
        "verify-against-engineering-standards",
    }
)
_BLOCKING_SKILLS = frozenset(
    {
        "maintain-canonical-requirements",
        "generate-implementation-design",
        "inspect-quality-gates",
    }
)
_DEFAULT_PORTABLE_SKILLS = _BLOCKING_SKILLS | {"chat-first-development"}
_EXTERNAL_EFFECT_SIDE_EFFECTS = frozenset(
    {"repository-and-authorized-external-write", "target-command-effects"}
)

POLICY_SCAN_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".qnt",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

_POLICY_SUBJECTS = (
    r"(?<![A-Za-z0-9_])(?:ci(?:/cd)?(?:\s+workflow)?|github\s+actions?|required\s+checks?|"
    r"status\s+checks?|branch\s+(?:protection|rules?|rulesets?|topology|"
    r"strategy|naming|patterns?)|rulesets?|merge\s+(?:rules?|queue|method|"
    r"strategy|target|base|commits?)|(?:squash|rebase|fast[- ]forward|no[- ]ff)\s+merge|"
    r"commit\s+(?:message|format|style|convention|policy)|pr\s+templates?|"
    r"(?:pull|merge)\s+request\s+templates?|review(?:er)?\s+"
    r"(?:count|approvals?)|approval\s+count)(?![A-Za-z0-9_])"
)

_FORCING_WORDS = (
    r"(?:\b(?:must|mandatory|shall|enforce[sd]?|require[sd]?|configure[sd]?|"
    r"enable[sd]?|install(?:ed)?|create[sd]?|add(?:ed)?|run|use[sd]?|apply|applied|"
    r"block(?:ing|ed)?|"
    r"gate[sd]?|prerequisite)\b|\b(?:is|are|be|becomes?|remains?)\s+required\b|"
    r"\bset(?:s)?\s+(?:up|to)\b|必須|要求(?:する|し|され)|強制(?:する|し|され)|"
    r"設定(?:する|し|せよ)|有効化(?:する|し|せよ)|導入(?:する|し|せよ)|"
    r"作成(?:する|し|せよ)|追加(?:する|し|せよ)|前提(?:にする|とする|である)|"
    r"条件(?:にする|とする|である))"
)

_NEGATIVE_CONTEXT = re.compile(
    r"(?:\bdo\s+not\b.{0,120}\b(?:require[sd]?|add|change|create|enforce|configure|enable|"
    r"install|set|run|use|apply)\b|"
    r"\b(?:do|does|did|must|shall)\s+not\s+(?:require[sd]?|add|change|"
    r"create|enforce|configure|enable|install|set|run|use|apply)\b|\bnot\s+(?:required|mandatory|"
    r"enforced|a\s+prerequisite)\b|\bwithout\s+(?:requiring|adding|changing|"
    r"creating|enforcing|running|using|applying)\b|\bnever\s+(?:require|add|change|"
    r"create|enforce|run|use|apply)\b|"
    r"要求しない|要求もしない|必須(?:項目)?にしない|強制しない|"
    r"追加しない|追加も変更もしない|追加または変更していない|"
    r"追加承認なし|作成しない|作成も要求もしない|変更しない|変更もしない|"
    r"導入しない|前提にしない|条件にしない|必要はない|"
    r"強制していない|要求していない|持ち込まない|触れない|上書きしない|配布しない)",
    re.IGNORECASE,
)

_HOST_OWNED_CONTEXT = re.compile(
    r"(?:target[- ]owned|host[- ]owned|target repository(?:'s)?\s+(?:existing|"
    r"selected|owned)|existing\s+(?:project|repository|target)[- ]owned|"
    r"already\s+(?:exists|configured|selected)|existing\s+ci|"
    r"target\s+repository\s+has\s+(?:explicitly\s+)?selected\s+(?:that\s+|the\s+|its\s+)?"
    r"(?:commit\s+(?:style|format)|merge\s+(?:method|rule)|"
    r"(?:squash|rebase|fast[- ]forward|no[- ]ff)\s+merge|ci(?:/cd)?(?:\s+workflow)?|"
    r"branch\s+(?:rule|protection)|repository\s+policy)|"
    r"(?:commit\s+(?:style|format)|merge\s+(?:method|rule)|"
    r"(?:squash|rebase|fast[- ]forward|no[- ]ff)\s+merge|ci(?:/cd)?(?:\s+workflow)?|"
    r"branch\s+(?:rule|protection)|repository\s+policy).{0,80}when\s+the\s+"
    r"(?:user|target\s+repository)\s+(?:explicitly\s+)?(?:requests?|selects?)\s+it|"
    r"既存CI|対象(?:の)?repository(?:が|の)(?:既に|すでに|明示的に|選択した|所有する|"
    r"定める|持つ)|導入先(?:が|の)(?:既に|明示的に|選択した|所有する|定める|"
    r"持つ)|利用者(?:が|の)(?:明示的に)?(?:依頼|選択|指定|承認)した)",
    re.IGNORECASE,
)

_CLAUSE_SPLIT = re.compile(
    r"(?:[。；;]|\s+(?:and|but|while|however)\s+|、(?=\s*[A-Za-z])|"
    r"(?:が|けれども|ただし)(?=\s*(?:CI|GitHub|required|status|branch|merge|commit|PR)\b))",
    re.IGNORECASE,
)

_TRUE_WORDS = {
    "1",
    "active",
    "always",
    "block",
    "blocking",
    "enabled",
    "enforce",
    "enforced",
    "mandatory",
    "must",
    "on",
    "required",
    "true",
    "yes",
}
_FALSE_WORDS = {
    "",
    "0",
    "advisory",
    "disabled",
    "false",
    "host-owned",
    "none",
    "null",
    "off",
    "optional",
    "selected",
    "target-owned",
}


def _normalise_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _one_final_newline(text: str) -> str:
    return text.rstrip("\n") + "\n"


def without_generated_block(text: str) -> str:
    """Return the human-authored Skill manual with its generated block removed.

    A malformed or duplicated marker is rejected instead of silently changing
    the digest scope.  The returned text is LF-normalised with one final newline.
    """

    normalised = _normalise_newlines(text)
    starts = [match.start() for match in re.finditer(re.escape(GENERATED_BLOCK_START), normalised)]
    ends = [match.end() for match in re.finditer(re.escape(GENERATED_BLOCK_END), normalised)]
    if not starts and not ends:
        return _one_final_newline(normalised)
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError("SKILL.md has malformed or duplicate generated contract markers")

    before = normalised[: starts[0]].rstrip("\n")
    after = normalised[ends[0] :].lstrip("\n")
    if before and after:
        return _one_final_newline(f"{before}\n\n{after}")
    return _one_final_newline(before or after)


def manual_body_sha256(text: str) -> str:
    """Digest the host-neutral, human-authored portion of a Skill manual."""

    body = without_generated_block(text)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_manual_host_paths(text: str, label: str = "SKILL.md") -> list[str]:
    """Reject host-specific Skill roots instead of normalizing digest input."""

    errors: list[str] = []
    body = without_generated_block(text)
    for line_number, line in enumerate(body.splitlines(), start=1):
        if _HOST_SPECIFIC_SKILL_PATH.search(line):
            errors.append(
                f"{label}:{line_number}: Skill manual must use <host-skill-path> "
                "instead of a host-specific Skill root"
            )
    return errors


def interface_sha256(skill_root: Path) -> str:
    """Digest the raw OpenAI interface file for ``skill_root``."""

    path = _safe_asset_path(skill_root, "agents/openai.yaml")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_asset_path(skill_root: Path, value: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"{value!r}: requiredAsset must be a normal relative path")

    root = skill_root.resolve(strict=True)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"{value!r}: requiredAsset must not traverse a symlink")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(f"{value!r}: requiredAsset is missing or escapes the Skill root") from exc
    if not resolved.is_file():
        raise ValueError(f"{value!r}: requiredAsset must name a regular file")
    return resolved


def skill_payload_inventory(skill_root: Path) -> list[str]:
    """List every distributable supporting file below one Skill root.

    ``SKILL.md`` and the separately-bound OpenAI interface are excluded. Python
    bytecode caches are runtime debris and are not part of a distributable Skill.
    Everything else must be declared explicitly in ``requiredAssets`` so an
    unreviewed file cannot enter the payload without changing the Quint contract.
    """

    if skill_root.is_symlink() or not skill_root.is_dir():
        raise ValueError(f"{skill_root}: Skill root must be a regular directory")
    inventory: list[str] = []
    for path in sorted(skill_root.rglob("*")):
        relative = path.relative_to(skill_root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"{relative.as_posix()!r}: Skill payload must not contain symlinks")
        if path.is_dir():
            continue
        value = relative.as_posix()
        if value in {"SKILL.md", "agents/openai.yaml"}:
            continue
        if not path.is_file():
            raise ValueError(f"{value!r}: Skill payload entry must be a regular file")
        inventory.append(value)
    return inventory


def payload_sha256(contract: Mapping[str, Any], skill_root: Path) -> str:
    """Digest the exact ``requiredAssets`` payload declared by a contract.

    The manifest itself is canonical JSON and contains a raw SHA-256 for each
    file.  Paths are sorted so Quint collection ordering cannot affect the result.
    Manual and interface content are intentionally covered by their own digests.
    """

    name = contract.get("name")
    values = contract.get("requiredAssets")
    if not isinstance(name, str) or not name:
        raise ValueError("Skill contract has no name")
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"{name}: requiredAssets must be a list of relative file paths")
    if len(values) != len(set(values)):
        raise ValueError(f"{name}: requiredAssets contains duplicate paths")

    declared = set(values)
    actual = set(skill_payload_inventory(skill_root))
    if declared != actual:
        raise ValueError(
            f"{name}: requiredAssets inventory drift: "
            f"undeclared={sorted(actual - declared)} stale={sorted(declared - actual)}"
        )

    assets = []
    for value in sorted(values):
        path = _safe_asset_path(skill_root, value)
        assets.append({"path": value, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"assets": assets, "skill": name}
    encoded = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _markdown_list(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "なし"
    return ", ".join(f"`{str(value).replace('`', '')}`" for value in values)


def _typed_bool(contract: Mapping[str, Any], field: str) -> bool:
    value = contract.get(field)
    if type(value) is not bool:
        raise ValueError(f"{contract.get('name', '<unknown>')}: {field} must be boolean")
    return value


def _repository_policy(contract: Mapping[str, Any]) -> Mapping[str, bool]:
    name = contract.get("name", "<unknown>")
    policy = contract.get("repositoryPolicy")
    if not isinstance(policy, Mapping) or set(policy) != set(REPOSITORY_POLICY_FIELDS):
        actual = sorted(map(str, policy)) if isinstance(policy, Mapping) else []
        raise ValueError(
            f"{name}: repositoryPolicy fields drift: "
            f"expected={list(REPOSITORY_POLICY_FIELDS)} actual={actual}"
        )
    for field in REPOSITORY_POLICY_FIELDS:
        if type(policy[field]) is not bool:
            raise ValueError(f"{name}: repositoryPolicy.{field} must be boolean")
    return policy  # type: ignore[return-value]


def validate_skill_contract(contract: Any) -> None:
    """Fail closed on one extracted ``SkillContract`` record.

    Quint 0.32 has no string-length or regular-expression operators.  Digest
    shape and the exact JSON-facing field types are therefore checked at this
    extraction/rendering boundary, while Quint remains authoritative for the
    state-machine invariants.
    """

    if not isinstance(contract, Mapping):
        raise ValueError("Skill contract must be an object")
    actual_fields = set(contract)
    if actual_fields != SKILL_CONTRACT_FIELDS:
        raise ValueError(
            "Skill contract fields drift: "
            f"missing={sorted(SKILL_CONTRACT_FIELDS - actual_fields)} "
            f"unknown={sorted(map(str, actual_fields - SKILL_CONTRACT_FIELDS))}"
        )

    name = contract["name"]
    if not isinstance(name, str) or not _SKILL_NAME_RE.fullmatch(name):
        raise ValueError("Skill contract name must be a lowercase portable identifier")

    for field in _CONTRACT_STRING_FIELDS:
        value = contract[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}: {field} must be non-empty text")
    for field in _CONTRACT_BOOLEAN_FIELDS:
        if type(contract[field]) is not bool:
            raise ValueError(f"{name}: {field} must be boolean")
    for field in _CONTRACT_LIST_FIELDS:
        values = contract[field]
        if type(values) is not list or not all(
            isinstance(value, str) and bool(value.strip()) for value in values
        ):
            raise ValueError(f"{name}: {field} must be a list of non-empty strings")
        if field in _NONEMPTY_CONTRACT_LIST_FIELDS and not values:
            raise ValueError(f"{name}: {field} must not be empty")
        if len(values) != len(set(values)):
            raise ValueError(f"{name}: {field} must contain unique values")
    for field in _DIGEST_FIELDS:
        value = contract[field]
        if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
            raise ValueError(
                f"{name}: {field} must be exactly 64 lowercase hexadecimal characters"
            )

    policy = _repository_policy(contract)
    enabled = [field for field in REPOSITORY_POLICY_FIELDS if policy[field]]
    if enabled:
        raise ValueError(f"{name}: repository policy must remain host-owned: {enabled}")

    if contract["pillar"] not in _ALLOWED_PILLARS:
        raise ValueError(f"{name}: pillar is outside the typed enum")
    if contract["applicability"] not in _ALLOWED_APPLICABILITY:
        raise ValueError(f"{name}: applicability is outside the typed enum")
    unknown_contexts = set(contract["activationContexts"]) - _ALLOWED_ACTIVATION_CONTEXTS
    if unknown_contexts:
        raise ValueError(f"{name}: activationContexts are outside the typed enum: {sorted(unknown_contexts)}")
    if contract["authority"] not in _ALLOWED_AUTHORITIES:
        raise ValueError(f"{name}: authority is outside the typed enum")
    if contract["sideEffect"] not in _ALLOWED_SIDE_EFFECTS:
        raise ValueError(f"{name}: sideEffect is outside the typed enum")
    if contract["failureState"] not in _ALLOWED_FAILURE_STATES:
        raise ValueError(f"{name}: failureState is outside the typed enum")
    if contract["guardrail"] != contract["repositoryBlocking"]:
        raise ValueError(f"{name}: guardrail and repositoryBlocking must be equivalent")
    if contract["guardrail"] and contract["pillar"] not in _GUARDRAIL_PILLARS:
        raise ValueError(f"{name}: a guardrail must belong to one of the three pillars")
    expected_external = contract["sideEffect"] in _EXTERNAL_EFFECT_SIDE_EFFECTS
    if contract["externalEffect"] != expected_external:
        raise ValueError(f"{name}: externalEffect does not match the runner side-effect capability")


def _dependency_cycle(graph: Mapping[str, list[str]]) -> list[str] | None:
    visited: set[str] = set()
    active: list[str] = []

    def visit(name: str) -> list[str] | None:
        if name in active:
            start = active.index(name)
            return [*active[start:], name]
        if name in visited:
            return None
        active.append(name)
        for dependency in graph[name]:
            cycle = visit(dependency)
            if cycle is not None:
                return cycle
        active.pop()
        visited.add(name)
        return None

    for name in graph:
        cycle = visit(name)
        if cycle is not None:
            return cycle
    return None


def validate_contract_catalog(contracts: Any) -> None:
    """Validate the complete 18-Skill catalog before extraction or rendering."""

    if type(contracts) is not list:
        raise ValueError("Skill catalog contracts must be a list")
    for contract in contracts:
        validate_skill_contract(contract)

    names = [contract["name"] for contract in contracts]
    if len(names) != len(set(names)):
        raise ValueError("Skill catalog names must be unique")
    actual_names = set(names)
    if len(names) != 18 or actual_names != EXPECTED_SKILL_NAMES:
        raise ValueError(
            "Skill catalog must contain exactly the expected 18 Skills: "
            f"missing={sorted(EXPECTED_SKILL_NAMES - actual_names)} "
            f"unknown={sorted(actual_names - EXPECTED_SKILL_NAMES)}"
        )

    by_name = {contract["name"]: contract for contract in contracts}
    graph = {contract["name"]: list(contract["dependencies"]) for contract in contracts}
    for name, dependencies in graph.items():
        unknown = set(dependencies) - actual_names
        if unknown:
            raise ValueError(f"{name}: dependencies reference unknown Skills: {sorted(unknown)}")
        if name in dependencies:
            raise ValueError(f"{name}: a Skill must not depend on itself")
    cycle = _dependency_cycle(graph)
    if cycle is not None:
        raise ValueError(f"Skill dependencies contain a cycle: {' -> '.join(cycle)}")

    for name, contract in by_name.items():
        expected_blocking = name in _BLOCKING_SKILLS
        if contract["guardrail"] != expected_blocking:
            raise ValueError(f"{name}: only the three named pillars may be guardrails")
        if contract["repositoryBlocking"] != expected_blocking:
            raise ValueError(f"{name}: repositoryBlocking is outside the three-pillar boundary")
        if contract["defaultPortable"] != (name in _DEFAULT_PORTABLE_SKILLS):
            raise ValueError(f"{name}: defaultPortable must contain only the entry and three pillars")
        expected_dependencies = _BLOCKING_SKILLS if name == "chat-first-development" else frozenset()
        if set(contract["dependencies"]) != expected_dependencies:
            raise ValueError(f"{name}: dependencies must contain only hard-required Skill edges")

    for pillar in _GUARDRAIL_PILLARS:
        matching = [
            contract
            for contract in contracts
            if contract["guardrail"] and contract["pillar"] == pillar
        ]
        if len(matching) != 1:
            raise ValueError(f"pillar {pillar!r} must have exactly one guardrail")
    if sum(bool(contract["externalEffect"]) for contract in contracts) != 3:
        raise ValueError("exactly three contracts must declare external-effect capability")


def _policy_markdown(contract: Mapping[str, Any]) -> str:
    policy = _repository_policy(contract)
    return ", ".join(
        f"`{field}={str(policy[field]).lower()}`" for field in REPOSITORY_POLICY_FIELDS
    )


def render_skill_block(contract: Mapping[str, Any]) -> str:
    """Render the activation boundary; keep audit detail in the catalog view."""

    validate_skill_contract(contract)
    fields: list[tuple[str, str]] = [
        ("Skill", f"`{contract.get('name', '')}`"),
        ("柱", str(contract.get("pillar", ""))),
        (
            "repository blocking",
            "yes" if _typed_bool(contract, "repositoryBlocking") else "no",
        ),
        ("既定portable", "yes" if _typed_bool(contract, "defaultPortable") else "no"),
        ("適用条件", str(contract.get("applicability", ""))),
        ("起動context", _markdown_list(contract.get("activationContexts"))),
        (
            "外部作用capability",
            "yes" if _typed_bool(contract, "externalEffect") else "no",
        ),
        ("Authority", str(contract.get("authority", ""))),
        ("副作用", str(contract.get("sideEffect", ""))),
        ("失敗状態", str(contract.get("failureState", ""))),
    ]
    lines = [
        GENERATED_BLOCK_START,
        "## Quint contract（自動生成）",
        "",
        "このblockは`spec/skills/skills.qnt`から自動生成し、直接編集しません。",
        "詳細・要件trace・digestは`spec/skills/skills.json`の同名契約を、契約の保守・監査時だけ参照します。",
        "repository policyは導入先が所有します。非該当ならartifactやblocking判定を作りません。",
        "",
    ]
    lines.extend(f"- {label}: {value}" for label, value in fields)
    lines += [GENERATED_BLOCK_END]
    return "\n".join(lines) + "\n"


def render_skill_manual(text: str, contract: Mapping[str, Any]) -> str:
    """Return a manual with one current generated block appended."""

    body = without_generated_block(text).rstrip("\n")
    return f"{body}\n\n{render_skill_block(contract)}"


def render_skills(catalog: Mapping[str, Any]) -> str:
    """Render the human-readable aggregate view from generated Skills JSON."""

    contracts = catalog.get("contracts")
    validate_contract_catalog(contracts)
    lines = [
        "<!-- tools/quintflow.pyによる自動生成。spec/skills/skills.qntを編集すること。 -->",
        "# Skills形式仕様",
        "",
        "全Skillの機械可読契約と、モデル化した3本柱の不変条件を人向けに表示した派生文書です。",
        "",
        "- 正本: `spec/skills/skills.qnt`",
        f"- Quint: `{catalog.get('quint_version', '')}`",
        f"- Skill数: {len(contracts)}",
        "",
        "| Skill | 役割 | 柱 | Guardrail | 既定portable | 起動context |",
        "|---|---|---|---|---|---|",
    ]
    pillar_labels = {
        "requirements": "要件正本",
        "design": "as-built設計",
        "checks": "選択check",
        "auxiliary": "補助",
    }
    for contract in contracts:
        _repository_policy(contract)
        lines.append(
            f"| `{contract['name']}` | {contract['role']} | "
            f"{pillar_labels[contract['pillar']]} | "
            f"{'blocking' if _typed_bool(contract, 'guardrail') else 'なし'} | "
            f"{'含む' if _typed_bool(contract, 'defaultPortable') else '含めない'} | "
            f"{_markdown_list(contract.get('activationContexts'))} |"
        )
    lines += [
        "",
        "## 検証する不変条件",
        "",
        "- 全Skill directoryと形式契約が1対1で対応する。",
        "- blocking guardrailは要件正本、as-built設計、選択checkの3本柱だけに属する。",
        "- portable契約はCI workflow、branch rule、merge方式、commit規約を要求しない。",
        "- 既定portable setは入口Skillと3本柱の4 Skillだけである。",
        "- 各柱は現在の変更へ非該当なら明示的にskipし、該当する柱の順序を飛び越えない。",
        "- 各Skillの7つのrepository policy fieldはfalseで、導入先の所有権を維持する。",
        "- `externalEffect` は外部作用が生じ得るrunner capabilityを追跡し、falseは未モデル化の外部作用が存在しないことまで保証しない。",
        "- Skill本文、必須asset、interfaceのdigestが形式契約と一致する。",
        "",
        "## 各Skillの契約",
    ]
    for contract in contracts:
        lines += [
            "",
            f"### {contract['name']}",
            "",
            f"- 前提: {contract['precondition']}",
            f"- 事後条件: {contract['postcondition']}",
            f"- 適用条件: `{contract.get('applicability', '')}`",
            f"- 起動context: {_markdown_list(contract.get('activationContexts'))}",
            f"- Authority: `{contract['authority']}`",
            f"- 副作用: `{contract['sideEffect']}`",
            f"- 外部作用capability: `{str(_typed_bool(contract, 'externalEffect')).lower()}`",
            f"- Guardrail / repository blocking / 既定portable: "
            f"`{str(_typed_bool(contract, 'guardrail')).lower()}` / "
            f"`{str(_typed_bool(contract, 'repositoryBlocking')).lower()}` / "
            f"`{str(_typed_bool(contract, 'defaultPortable')).lower()}`",
            f"- Repository policy: {_policy_markdown(contract)}",
            f"- 失敗状態: `{contract.get('failureState', '')}`",
            f"- 入力: {_markdown_list(contract['inputs'])}",
            f"- 出力: {_markdown_list(contract['outputs'])}",
            f"- 義務: {_markdown_list(contract.get('obligationIds', contract.get('obligations')))}",
            f"- 禁止事項: {_markdown_list(contract.get('prohibitions'))}",
            f"- 依存Skill: {_markdown_list(contract.get('dependencies'))}",
            f"- 必須asset: {_markdown_list(contract.get('requiredAssets'))}",
            f"- 要件trace: {_markdown_list(contract.get('requirementIds'))}",
            f"- manual digest: `{contract['manualBodySha256']}`",
            f"- payload digest: `{contract['payloadSha256']}`",
            f"- interface digest: `{contract['interfaceSha256']}`",
        ]
    return "\n".join(lines) + "\n"


def _policy_clauses(text: str) -> Iterable[tuple[int, str]]:
    for line_number, line in enumerate(_normalise_newlines(text).splitlines(), start=1):
        for clause in _CLAUSE_SPLIT.split(line):
            value = clause.strip()
            if value:
                yield line_number, value


def validate_manual_policy(text: str, label: str = "text") -> list[str]:
    """Return prose policy violations without rejecting bounded mentions.

    Negative statements and statements explicitly delegating a policy to an
    existing/selected target-owned rule are accepted.  Clause-level matching is
    important: ``do not add CI and require merge queue`` still has one violation.
    """

    errors: list[str] = []
    subject_then_force = re.compile(rf"{_POLICY_SUBJECTS}.{{0,100}}{_FORCING_WORDS}", re.IGNORECASE)
    force_then_subject = re.compile(rf"{_FORCING_WORDS}.{{0,100}}{_POLICY_SUBJECTS}", re.IGNORECASE)
    for line_number, clause in _policy_clauses(text):
        if not (subject_then_force.search(clause) or force_then_subject.search(clause)):
            continue
        if _NEGATIVE_CONTEXT.search(clause):
            continue
        if _HOST_OWNED_CONTEXT.search(clause):
            continue
        errors.append(f"{label}:{line_number}: portable asset appears to require repository policy: {clause}")
    return errors


def _normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _is_false_value(value: Any) -> bool:
    if value is None or value is False or value == 0:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _FALSE_WORDS
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _is_truthy_policy_value(value: Any) -> bool:
    if _is_false_value(value):
        return False
    if value is True or (isinstance(value, (int, float)) and value != 0):
        return True
    if isinstance(value, str):
        return value.strip().lower() not in _FALSE_WORDS
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return False


def _path_is_repository_policy(path: Sequence[str]) -> bool:
    keys = [_normalise_key(part) for part in path if part]
    joined = "".join(keys)
    canonical_policy_fields = {
        "branchprotection",
        "ciworkflow",
        "commitformat",
        "mergestrategy",
        "prtemplate",
        "requiredcheck",
        "ruleset",
    }
    exact = {
        "approvalcount",
        "branchprotection",
        "branchprotectionenabled",
        "branchrule",
        "branchrules",
        "cirequired",
        "ciworkflow",
        "commitformat",
        "commitmessagepattern",
        "commitpolicy",
        "enforceci",
        "githubactionsrequired",
        "mandatoryci",
        "mergebase",
        "mergemethod",
        "mergequeue",
        "mergequeueenabled",
        "mergerequired",
        "mergerule",
        "mergerules",
        "mergestrategy",
        "minimumapprovals",
        "minapprovals",
        "prtemplate",
        "prtemplaterequired",
        "requiredapprovals",
        "requiredcheck",
        "requiredchecks",
        "requiredstatuschecks",
        "requireci",
        "requiresci",
        "requiresmergerule",
        "ruleset",
        "rulesets",
        "statuscheck",
        "statuschecks",
    }
    flattened_policy_prefix = "repositorypolicy"
    if (
        any(key in exact for key in keys)
        or joined in exact
        or any(
            key.startswith(flattened_policy_prefix)
            and key[len(flattened_policy_prefix) :] in canonical_policy_fields
            for key in keys
        )
    ):
        return True
    pairs = set(zip(keys, keys[1:]))
    triples = set(zip(keys, keys[1:], keys[2:]))
    return bool(
        ("github", "actions", "required") in triples
        or
        pairs
        & {
            ("ci", "enabled"),
            ("ci", "enforced"),
            ("ci", "mandatory"),
            ("ci", "required"),
            ("commit", "format"),
            ("commit", "policy"),
            ("merge", "method"),
            ("merge", "queue"),
            ("merge", "required"),
            ("merge", "rule"),
            ("branch", "protection"),
            ("branch", "required"),
            ("branch", "rule"),
            ("pullrequest", "template"),
            ("required", "checks"),
            ("status", "checks"),
        }
    )


def _value_requires_ci(path: Sequence[str], value: Any) -> bool:
    if not isinstance(value, str):
        return False
    compact = _normalise_key(value)
    if compact not in {"ci", "cicd", "githubaction", "githubactions"}:
        return False
    context = {_normalise_key(part) for part in path}
    return any(
        part in {"check", "checks", "evidence", "gate", "required", "verification", "verifier"}
        or part.endswith(("check", "checks", "evidence", "gate", "verification", "verifier"))
        for part in context
    )


def _structured_leaf_errors(path: Sequence[str], value: Any, label: str) -> list[str]:
    dotted = ".".join(path) or "<root>"
    if _path_is_repository_policy(path) and _is_truthy_policy_value(value):
        return [f"{label}:{dotted}: structured asset enables repository policy with {value!r}"]
    if _value_requires_ci(path, value):
        return [f"{label}:{dotted}: structured asset makes CI the verification mechanism"]
    return []


def _walk_structured(value: Any, path: tuple[str, ...], label: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = (*path, key_text)
            if not isinstance(child, (dict, list)):
                errors.extend(_structured_leaf_errors(child_path, child, label))
            else:
                errors.extend(_walk_structured(child, child_path, label))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = (*path, str(index))
            if isinstance(child, (dict, list)):
                errors.extend(_walk_structured(child, child_path, label))
            else:
                errors.extend(_structured_leaf_errors(path, child, label))
    return errors


def _strip_yaml_quoted_portions(line: str) -> str:
    result: list[str] = []
    quote = ""
    escaped = False
    for character in line:
        if quote:
            if escaped:
                escaped = False
            elif character == "\\" and quote == '"':
                escaped = True
            elif character == quote:
                quote = ""
            result.append(" ")
        elif character in {'"', "'"}:
            quote = character
            result.append(" ")
        elif character == "#":
            break
        else:
            result.append(character)
    return "".join(result)


def _yaml_scalar(value: str) -> Any:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        if stripped[0] == '"':
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return stripped[1:-1]
        return stripped[1:-1].replace("''", "'")
    lowered = stripped.lower()
    if lowered in {"null", "~"}:
        return None
    if lowered in {"true", "yes", "on"}:
        return True
    if lowered in {"false", "no", "off"}:
        return False
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", stripped):
        return float(stripped) if "." in stripped else int(stripped)
    return stripped


def _yaml_errors(text: str, label: str) -> list[str]:
    errors: list[str] = []
    stack: list[tuple[int, str]] = []
    key_pattern = re.compile(r"^(?P<indent> *)(?:- )?(?P<key>[A-Za-z0-9_.-]+):(?P<value>.*)$")
    quoted_key = re.compile(r"^\s*(?:-\s+)?['\"][^'\"]+['\"]\s*:")
    for line_number, original in enumerate(_normalise_newlines(text).splitlines(), start=1):
        if not original.strip() or original.lstrip().startswith("#"):
            continue
        if "\t" in original[: len(original) - len(original.lstrip())]:
            errors.append(f"{label}:{line_number}: YAML indentation must not contain tabs")
            continue
        if quoted_key.match(original):
            errors.append(f"{label}:{line_number}: quoted YAML mapping keys are not auditable")
            continue
        structural = _strip_yaml_quoted_portions(original)
        if any(character in structural for character in "{}[]"):
            errors.append(f"{label}:{line_number}: YAML flow collections are not auditable")
            continue
        if re.search(r"(?:^|\s)[&*!][A-Za-z0-9_-]+", structural) or re.search(r":\s*[>|][-+]?\s*$", structural):
            errors.append(f"{label}:{line_number}: YAML aliases, tags, and block scalars are not auditable")
            continue

        match = key_pattern.match(original)
        if match:
            indent = len(match.group("indent"))
            key = match.group("key")
            while stack and stack[-1][0] >= indent:
                stack.pop()
            path = tuple(value for _, value in stack) + (key,)
            raw_value = match.group("value").strip()
            if raw_value:
                errors.extend(_structured_leaf_errors(path, _yaml_scalar(raw_value), label))
            else:
                stack.append((indent, key))
            continue

        list_match = re.match(r"^(?P<indent> *)-\s+(?P<value>.+)$", original)
        if list_match:
            indent = len(list_match.group("indent"))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            errors.extend(
                _structured_leaf_errors(
                    tuple(value for _, value in stack),
                    _yaml_scalar(list_match.group("value")),
                    label,
                )
            )
            continue
        errors.append(f"{label}:{line_number}: YAML line is outside the auditable plain-block subset")
    return errors


def _ast_path(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        parent = _ast_path(node.value)
        return (*parent, node.attr) if parent else None
    if isinstance(node, ast.Subscript):
        parent = _ast_path(node.value)
        if not parent:
            return None
        try:
            key = ast.literal_eval(node.slice)
        except (ValueError, TypeError):
            return parent
        return (*parent, str(key))
    return None


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return "<dynamic>"


def _command_tokens(node: ast.AST) -> tuple[list[str], bool] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return shlex.split(node.value), False
        except ValueError:
            return None
    if isinstance(node, ast.JoinedStr):
        command = "".join(
            value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else " <dynamic> "
            for value in node.values
        )
        try:
            return shlex.split(command), True
        except ValueError:
            return None
    if isinstance(node, (ast.List, ast.Tuple)):
        tokens: list[str] = []
        dynamic = False
        for item in node.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                tokens.append(item.value)
            else:
                tokens.append("<dynamic>")
                dynamic = True
        return tokens, dynamic
    return None


def _gh_api_endpoint(tokens: Sequence[str]) -> str | None:
    """Return the positional ``gh api`` endpoint, preserving a dynamic marker."""

    value_options = {
        "-f",
        "-h",
        "-x",
        "--cache",
        "--field",
        "--header",
        "--hostname",
        "--input",
        "--method",
        "--preview",
        "--raw-field",
    }
    index = 2
    while index < len(tokens):
        token = tokens[index]
        lowered = token.lower()
        if lowered in value_options:
            index += 2
            continue
        if lowered.startswith("--") and "=" in lowered:
            index += 1
            continue
        if lowered.startswith(("-f", "-h", "-x")) and len(lowered) > 2:
            index += 1
            continue
        if lowered.startswith("-"):
            index += 1
            continue
        return token
    return None


def _resolve_import_alias(
    path: tuple[str, ...],
    aliases: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    replacement = aliases.get(path[0])
    if replacement is None:
        return path
    return (*replacement, *path[1:])


def _gh_api_policy_write(
    node: ast.Call,
    aliases: Mapping[str, tuple[str, ...]],
) -> bool:
    path = _ast_path(node.func)
    if not path:
        return False
    path = _resolve_import_alias(path, aliases)
    root = _normalise_key(path[0])
    name = _normalise_key(path[-1])
    subprocess_call = root == "subprocess" and name in {
        "call",
        "checkcall",
        "checkoutput",
        "popen",
        "run",
    }
    literal_shell_call = root == "os" and name == "system"
    if not subprocess_call and not literal_shell_call:
        return False
    command_node = node.args[0] if node.args else next(
        (keyword.value for keyword in node.keywords if keyword.arg == "args"),
        None,
    )
    if command_node is None:
        return False
    parsed = _command_tokens(command_node)
    if not parsed:
        return False
    tokens, dynamic = parsed
    if len(tokens) < 3 or Path(tokens[0]).name.lower() != "gh" or tokens[1].lower() != "api":
        return False

    method = "GET"
    method_is_dynamic = False
    explicit_method = False
    implicit_post = False
    for index, token in enumerate(tokens[2:], start=2):
        lowered = token.lower()
        if lowered in {"-x", "--method"} and index + 1 < len(tokens):
            explicit_method = True
            if tokens[index + 1] == "<dynamic>":
                method_is_dynamic = True
            else:
                method = tokens[index + 1].upper()
        elif lowered.startswith("--method="):
            explicit_method = True
            method = token.split("=", 1)[1].upper()
        elif lowered.startswith("-x") and len(token) > 2:
            explicit_method = True
            method = token[2:].upper()
        if (
            lowered in {"-f", "--field", "--input", "--raw-field"}
            or lowered.startswith(("-f", "--field=", "--input=", "--raw-field="))
        ):
            implicit_post = True
    if not explicit_method and implicit_post:
        method = "POST"
    write_method = method in {"DELETE", "PATCH", "POST", "PUT"}
    if not write_method and not method_is_dynamic:
        return False

    endpoint = _gh_api_endpoint(tokens)
    command = " ".join(tokens[2:]).lower().replace("_", "-")
    policy_endpoint = re.compile(
        r"(?:branches?/[^ ]+/protection|branch[- /]+protection|required[- /]+status[- /]+checks?|"
        r"rulesets?|merge[- /]+queue)"
    )
    if policy_endpoint.search(command) is not None:
        return True
    endpoint_is_dynamic = endpoint == "<dynamic>"
    return dynamic and endpoint_is_dynamic and (write_method or method_is_dynamic)


def _python_errors(text: str, label: str) -> list[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"{label}:{exc.lineno or 1}: Python asset is not parseable: {exc.msg}"]

    aliases: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for imported in node.names:
                root = imported.name.split(".", 1)[0]
                if root not in {"os", "subprocess"}:
                    continue
                local = imported.asname or root
                aliases[local] = (root,)
        elif isinstance(node, ast.ImportFrom) and node.module in {"os", "subprocess"}:
            for imported in node.names:
                if imported.name == "*":
                    continue
                local = imported.asname or imported.name
                aliases[local] = (node.module, imported.name)

    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets: list[ast.AST]
            if isinstance(node, ast.Assign):
                targets = node.targets
                value_node = node.value
            else:
                targets = [node.target]
                value_node = node.value
            value = _literal(value_node) if value_node is not None else "<dynamic>"
            walked_literal = False
            for target in targets:
                path = _ast_path(target)
                if path:
                    errors.extend(_structured_leaf_errors(path, value, f"{label}:{node.lineno}"))
                    if isinstance(value, dict):
                        errors.extend(_walk_structured(value, path, f"{label}:{node.lineno}"))
                        walked_literal = True
            if isinstance(value, dict) and not walked_literal:
                errors.extend(_walk_structured(value, (), f"{label}:{node.lineno}"))
        elif isinstance(node, ast.Dict):
            value = _literal(node)
            if isinstance(value, dict):
                errors.extend(_walk_structured(value, (), f"{label}:{node.lineno}"))
        elif isinstance(node, ast.Call):
            path = _ast_path(node.func)
            if not path:
                continue
            name = _normalise_key(path[-1])
            call_label = f"{label}:{node.lineno}:{'.'.join(path)}"
            if _gh_api_policy_write(node, aliases):
                errors.append(f"{call_label}: Python asset writes repository policy with gh api")
                continue
            if name in {
                "enablebranchprotection",
                "enforceci",
                "enforcemergequeue",
                "requireci",
                "setmergequeue",
                "setrequiredchecks",
                "updatebranchprotection",
            }:
                errors.append(f"{call_label}: Python asset configures repository policy")
                continue
            if name in {"configureci", "configuremerge", "configuremergequeue", "configurebranchprotection"}:
                if not node.keywords:
                    errors.append(f"{call_label}: Python asset configures repository policy")
                    continue
                policy_root = {
                    "configureci": ("ci",),
                    "configuremerge": ("merge",),
                    "configuremergequeue": ("merge", "queue"),
                    "configurebranchprotection": ("branch", "protection"),
                }[name]
                for keyword in node.keywords:
                    if keyword.arg is None:
                        errors.append(f"{call_label}: dynamic repository-policy arguments are not auditable")
                        continue
                    errors.extend(
                        _structured_leaf_errors(
                            (*policy_root, keyword.arg),
                            _literal(keyword.value),
                            call_label,
                        )
                    )
    return errors


def validate_structured_policy(
    text_or_path: str | Path,
    label: str | None = None,
) -> list[str]:
    """Return repository-policy violations in JSON, YAML, TOML, or Python content."""

    if isinstance(text_or_path, Path):
        path = text_or_path
        text = path.read_text(encoding="utf-8")
        effective_label = label or path.as_posix()
        suffix = path.suffix.lower()
    else:
        text = text_or_path
        effective_label = label or "text"
        suffix = Path(effective_label).suffix.lower()

    if suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            return [f"{effective_label}:{exc.lineno}: JSON asset is not parseable: {exc.msg}"]
        return _walk_structured(value, (), effective_label)
    if suffix == ".toml":
        try:
            value = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            return [f"{effective_label}: TOML asset is not parseable: {exc}"]
        return _walk_structured(value, (), effective_label)
    if suffix in {".yaml", ".yml"}:
        return _yaml_errors(text, effective_label)
    if suffix == ".py":
        return _python_errors(text, effective_label)
    return []


def validate_policy_file(path: Path, label: str | None = None) -> list[str]:
    """Audit one portable text file with prose and format-aware policy checks."""

    if path.suffix.lower() not in POLICY_SCAN_SUFFIXES:
        return []
    effective_label = label or path.as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    prose = without_generated_block(text) if path.name == "SKILL.md" else text
    manual_errors = [] if path.suffix.lower() == ".py" else validate_manual_policy(prose, effective_label)
    host_path_errors = (
        validate_manual_host_paths(prose, effective_label)
        if path.name == "SKILL.md"
        else []
    )
    return [
        *manual_errors,
        *host_path_errors,
        *validate_structured_policy(text, effective_label),
    ]


def validate_policy_tree(root: Path) -> list[str]:
    """Audit all supported text leaves below an expanded portable tree."""

    errors: list[str] = []
    for path in sorted(root.rglob("*")):
        label = path.relative_to(root).as_posix()
        if path.is_symlink():
            errors.append(f"{label}: portable payload must not contain symlinks")
            continue
        if path.is_dir():
            continue
        errors.extend(validate_policy_file(path, label))
    return errors


def validate_skill_tree(skill_root: Path) -> list[str]:
    """Audit every portable Skill manual, reference, interface, asset, and script."""

    errors: list[str] = []
    for path in sorted(skill_root.rglob("*")):
        label = path.relative_to(skill_root.parent.parent).as_posix()
        if path.is_symlink():
            errors.append(f"{label}: portable Skill payload must not contain symlinks")
            continue
        if path.is_dir():
            continue
        errors.extend(validate_policy_file(path, label))
    return errors
