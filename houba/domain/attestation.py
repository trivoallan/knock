"""Build the in-toto Statement for houba's transform/hardening predicate (roadmap ①).

The annotation stamp (`stamp.py`) is the cheap index card; this is the heavy,
signable record it points at. Pure — no httpx / subprocess / os.environ, like
stamp.py. The predicate shape is a Pydantic model so its JSON Schema is derived,
never hand-written, and frozen as public API at /v1.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Frozen public API (spec Q1). A project-branded vanity URI (the convention SLSA
# itself follows with slsa.dev): it needn't resolve, stays stable across repo moves,
# and names no deploying org. Versioned at /v1.
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://houba.dev/predicate/transform/v1"


class TransformStepFact(BaseModel):
    """One resolved hardening step as recorded in the predicate (name + params)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class TransformPredicate(BaseModel):
    """houba's transform/hardening lineage — the novel fact BuildKit cannot know.

    Mirrors the `io.houba.*` annotation lineage, but signed and verifiable. `import`
    uses its public spelling (the same key as `io.houba.import`) via an alias.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    policy: str
    import_: str = Field(alias="import")
    variant: str
    source: str  # source repo, e.g. "docker.io/library/redis" — never a destination
    source_digest: str  # the immutable digest the rebuild derived from
    builder_id: str
    created: str  # ISO-8601 build time
    transform_version: str  # content hash of the resolved transform (== io.houba.transform.version)
    steps: list[TransformStepFact] = Field(default_factory=list)


def _subject_digest(digest: str) -> dict[str, str]:
    """`sha256:abc` -> `{"sha256": "abc"}` (the in-toto subject digest shape)."""
    algo, sep, value = digest.partition(":")
    if not sep:
        return {"sha256": algo}  # no algo prefix -> assume sha256
    return {algo: value}


def build_transform_statement(
    *,
    subject_name: str,
    subject_digest: str,
    policy: str,
    import_name: str,
    variant: str,
    source: str,
    source_digest: str,
    builder_id: str,
    created: str,
    transform_version: str,
    steps: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Assemble the in-toto Statement whose subject is the rebuilt output digest.

    Pure: callers pass already-resolved facts (digests, the ISO timestamp, the
    resolved steps). Returns a plain dict so an adapter can serialize it to JSON.
    """
    predicate = TransformPredicate.model_validate(
        {
            "import": import_name,
            "policy": policy,
            "variant": variant,
            "source": source,
            "source_digest": source_digest,
            "builder_id": builder_id,
            "created": created,
            "transform_version": transform_version,
            "steps": [TransformStepFact(name=n, params=p) for n, p in steps],
        }
    )
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": subject_name, "digest": _subject_digest(subject_digest)}],
        "predicateType": PREDICATE_TYPE,
        "predicate": predicate.model_dump(by_alias=True),
    }


def transform_predicate_json_schema() -> dict[str, Any]:
    """Published JSON Schema for the transform predicate (frozen public API /v1).

    Derived from the Pydantic model — never hand-written (CLAUDE.md).
    """
    return TransformPredicate.model_json_schema(by_alias=True)
