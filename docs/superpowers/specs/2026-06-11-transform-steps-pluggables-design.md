# Pluggable transform-step registry — design

> **Status:** approved design, pre-implementation. A **refactor delta** on top of
> [image transform / hardening (#24)](2026-06-11-image-transform-hardening-design.md),
> which is **merged** (`origin/main` `79e9dfa`). Terminal step after this spec: `writing-plans`.

## 1. Context

PR #24 shipped houba's **rebuild path**: a `MirrorPolicy` variant carrying a non-empty
`transform` is re-built through a generated hardening Dockerfile and stamped with transform
lineage, instead of byte-copied. It delivered two primitives (`injectCA`,
`rewritePackageSources`), env-roster resolution by name (`HOUBA_TRANSFORM_CA_CERTS`,
`HOUBA_TRANSFORM_PACKAGE_MIRRORS`), a content-hash `transform_version`, two-axis change
detection, and the copy/build branch in `reconcile`.

It is **functional but monolithic.** Adding one step today touches **five sites**:

| Site (merged code) | What is hardcoded |
| --- | --- |
| `domain/transform.py` `ALLOWED_STEPS` | the vocabulary tuple |
| `domain/transform.py` `validate_transform_steps` | `if/elif step.name` + inline param checks |
| `domain/transform.py` `render_dockerfile(source_ref, *, ca_cert_filenames, apt_mirror, apk_mirror)` | concrete signature + per-step branches |
| `domain/transform.py` `transform_version(steps, *, cert_contents, apt_mirror, apk_mirror)` | concrete hash payload |
| `use_cases/reconcile.py` `_resolve_transform` / `_ResolvedTransform` | `if/elif step.name` + concrete resolved fields |

This is exactly the friction roadmap ③ ("composable transformation primitives") targets. This
spec makes the step vocabulary **pluggable**: one new step = one self-contained unit, no edits
to the I/O plumbing. It also delivers the **discriminated-union JSON Schema** that #24
explicitly deferred and that CLAUDE.md mandates ("JSON Schema, systematically").

## 2. Scope

**In scope (this spec):**

- A **pure step-compiler registry** in `domain/` (one `TransformStepCompiler` per step name).
- **Per-step Pydantic params models** replacing the hand-rolled `if/elif` validation.
- A **`Fragment` / `ResourceRef`** contract: a step purely declares its named resource
  references and emits an ordered Dockerfile fragment + the context files it needs.
- **Resource-kind resolution** generalized in the application layer: one resolver **per kind**
  (`caCert`, `packageMirror`), not per step.
- The **discriminated-union JSON Schema** for the transform vocabulary.
- A third primitive, **`setTimezone`** (deferred by #24), added as the **proof** that a new
  step needs zero I/O-layer edits.

**Out of scope (already done in #24, kept as-is):** the rebuild engine, the env rosters and
name resolution, the `transform_version` *semantics*, two-axis change detection, the copy/build
branch, the stamp lineage (`io.houba.transform.steps` / `.version`), single-platform rebuild.

**Out of scope (deferred):** further primitives (`setLabel`, Java keystore, deb822
`rewritePackageSources`), new resource kinds, third-party entry-point plugins, a `run`
escape hatch (rejected — breaks introspectable provenance), multi-platform rebuild.

## 3. Decisions

| Fork | Decision | Why |
| --- | --- | --- |
| Keep #24 or refactor? | **Refactor to a pluggable registry** | #24 works but every new step is a 5-site change; the deferred backlog (`setTimezone`, `setLabel`, keystore, deb822) makes the registry pay off now, and the discriminated-union schema is owed regardless. |
| How to keep `domain/` pure while resolution does I/O? | **Split *step vocabulary* (pure, extensible) from *resource resolution* (I/O, per-kind)** | A step purely declares `ResourceRef(kind, name)` and emits a `Fragment` given already-resolved data. The app resolves refs by **kind** (2 kinds), so a new step reusing existing kinds — or needing none — adds **no I/O code**. Domain stays 100 % pure and the registry lives in `domain/`. The alternative (a per-step resolver in the registry) would drag I/O into `domain/` and is rejected. |
| Step params validation | **Per-step Pydantic model on each compiler**; `validate_transform_steps` becomes registry-driven | Removes the `if/elif`; same fail-fast point (load-and-validate plan phase) and same `PolicyValidationError`. |
| Published JSON Schema | **`oneOf` of `{stepName: <ParamsModel schema>}`, derived from the registry** | Closes the gap #24 deferred; "JSON Schema, systematically." |
| `transform_version` payload | **Generalize to `(names+params, resolved resources)`; accept a one-time re-hash** | Engine just merged, no production fleet; preserving exact bytes would couple the generic hasher to the two original kinds. Semantics ("changes iff the transform changes") preserved; the one-time rebuild wave is documented (§9). |
| Proof primitive | **`setTimezone`** (pure, no resources) | Demonstrates the seam: adding it is one pure class, zero I/O edits. `setLabel` rejected as the proof (it would muddy the stamp-vs-image-LABEL distinction). |

## 4. The pluggable contract (`domain/transforms/`, pure)

```python
# base.py — all pure, mypy --strict
@dataclass(frozen=True)
class ResourceRef:
    kind: str            # "caCert" | "packageMirror"  (resource-kind vocabulary)
    name: str            # the policy-level name; resolved by the application layer

@dataclass(frozen=True)
class ResolvedResource:  # what the app's per-kind resolver produced for a ref
    kind: str
    name: str
    filename: str | None = None   # caCert: e.g. "corp-root.crt"
    content: str | None = None    # caCert: PEM
    apt: str | None = None        # packageMirror
    apk: str | None = None        # packageMirror

@dataclass(frozen=True)
class ContextFile:
    path: str            # relative path inside the build context
    content: str

@dataclass(frozen=True)
class Fragment:
    instructions: tuple[str, ...]                  # ordered Dockerfile lines (no FROM)
    context_files: tuple[ContextFile, ...] = ()

class TransformStepCompiler(ABC):
    name: ClassVar[str]                            # YAML name, e.g. "injectCA"
    params_model: ClassVar[type[BaseModel]]
    def resource_refs(self, params: BaseModel) -> tuple[ResourceRef, ...]:
        return ()
    @abstractmethod
    def fragment(self, params: BaseModel, resources: tuple[ResolvedResource, ...]) -> Fragment: ...
        # `resources` are this step's resolved refs, **in the same order** as resource_refs(params)
```

A step receives **its own** resolved resources as an ordered tuple aligned with `resource_refs` —
**not** a global map. This removes any name-collision risk between kinds (a `caCert` and a
`packageMirror` may share a name; they come from different rosters) and lets the step `zip` against
its own params. `ResolvedResource` is a small tagged struct (mirrors `CACertSource`'s path|pem
style) — pragmatic for two kinds; per-kind typing is a later refinement if the kind set grows. The
registry stores compilers as `TransformStepCompiler` (the type-erasure point); each concrete
subclass stays concretely typed.

## 5. Registry & pure domain surface (`domain/transforms/`)

`domain/transform.py` (flat file) becomes a package:

```
houba/domain/transforms/
  base.py       # ResourceRef, ResolvedResource, ContextFile, Fragment, TransformStepCompiler
  steps.py      # InjectCA, RewritePackageSources, SetTimezone + their Params models
  registry.py   # BUILTIN_STEPS, Registry (get/names), DEFAULT_REGISTRY
  render.py     # validate_transform_steps, resource_refs, render, transform_version
  schema.py     # transform_steps_schema() — feeds mirror_policy_json_schema()
```

A `ResolvedStep` pairs a step with its resolved resources (built by the app, §6); `render` and
`transform_version` consume those — no parallel sequences, no keying:

```python
@dataclass(frozen=True)
class ResolvedStep:
    step: TransformStep
    resources: tuple[ResolvedResource, ...]   # in resource_refs order

@dataclass(frozen=True)
class Rendered:
    dockerfile: str                           # "FROM <source_ref>\n" + ordered fragment instructions
    context_files: tuple[ContextFile, ...]
```

Registry-driven, no `if/elif` on `step.name`:

```python
def validate_transform_steps(steps: list[TransformStep]) -> None: ...
    # name ∈ registry?  params valid against compiler.params_model?  else PolicyValidationError

def render(resolved_steps: Sequence[ResolvedStep], *, source_ref: str) -> Rendered: ...
    # concat compiler.fragment(params, rs.resources) in policy order, under one FROM

def transform_version(resolved_steps: Sequence[ResolvedStep]) -> str: ...
    # sha256 over canonical JSON: [[name, params, [resolved-resource fields…]] per step]
```

Canonical JSON: step order preserved (semantically ordered); object keys sorted. The hash still
changes when a step/param changes **or** a resolved value (cert content, mirror URL) changes.
(The app calls `compiler.resource_refs(params)` per step to know what to resolve — §6.)

## 6. Resource-kind resolution (application layer — the only remaining switch)

The single per-**kind** dispatch lives where I/O belongs (use case / a small app helper), reusing
#24's config resolvers verbatim:

```python
def resolve_ref(ref: ResourceRef, *, ca_certs, package_mirrors) -> ResolvedResource:
    if ref.kind == "caCert":
        (name, src), = resolve_ca_certs([ref.name], ca_certs)      # ConfigError on unknown name
        content = src.pem if src.pem is not None else _read_cert_file(src.path)  # ConfigError on unreadable
        return ResolvedResource("caCert", name, filename=f"{name}.crt", content=content)
    if ref.kind == "packageMirror":
        m = resolve_mirror(ref.name, package_mirrors)              # ConfigError on unknown name
        return ResolvedResource("packageMirror", ref.name, apt=m.apt, apk=m.apk)
    raise InternalError(f"no resolver for resource kind {ref.kind!r}")
```

`use_cases/reconcile.py` `_resolve_transform` collapses to: for each step, take
`compiler.resource_refs(params)`, `resolve_ref` each in order → `ResolvedStep(step, resources)`;
then `transform_version(resolved_steps)`. `_build_variant` calls `render(resolved_steps,
source_ref=…)`, writes `Rendered.context_files`, writes the Dockerfile, `build_and_push`. The
per-step `if/elif` and `_ResolvedTransform`'s concrete `cert_files/apt_mirror/apk_mirror` fields
are gone (replaced by the `list[ResolvedStep]`); resolution happens in the plan phase exactly as
today (all `ConfigError`s before any mutation).

## 7. Reference step compilers

| Step | Params | `resource_refs` | `fragment` |
| --- | --- | --- | --- |
| `injectCA` | `{certs: list[str]}` (≥ 1) | one `caCert` ref per name | `COPY <name>.crt … /usr/local/share/ca-certificates/` + `RUN update-ca-certificates`; one `ContextFile` per cert |
| `rewritePackageSources` | `{mirror: str}` | one `packageMirror` ref | the existing distro-agnostic `sed` `RUN` over apt `.list` / apk `repositories`, from the resolved `apt`/`apk` URLs; no context files |
| `setTimezone` **(new, proof)** | `{zone: str}` | none | `RUN ln -snf /usr/share/zoneinfo/<zone> /etc/localtime && echo <zone> > /etc/timezone` + `ENV TZ=<zone>`; no context files, no resolution |

`injectCA` and `rewritePackageSources` reproduce #24's exact emitted Dockerfile lines (behaviour
preserved). The Debian-family assumption and the deb822 limitation from #24 are unchanged.

## 8. JSON Schema (discriminated union)

`mirror_policy_json_schema()` replaces the open `TransformStep` definition with a `oneOf` of
`{<stepName>: <ParamsModel.model_json_schema()>}` branches, **derived from the registry** (never
hand-written), matching the authoring single-key-map YAML form. Editors/CI then validate
`injectCA: { certz: [...] }` pre-commit. `mirror_policy.py`'s `TransformStep` keeps its
`{name, params: dict}` runtime shape (no churn to merge/expand/variants); `validate_transform_steps`
stays the runtime gate.

## 9. Hash compatibility (one-time re-hash)

Generalizing the `transform_version` payload changes its serialized bytes versus #24. On the first
reconcile after deploy, every already-stamped transformed image has a recorded `transform.version`
that no longer matches the recomputed one → it rebuilds **once**, then stabilizes (idempotent
thereafter). This is accepted: the engine only just merged, there is no production fleet relying on
the exact bytes, and the hash *semantics* are preserved. Documented here and to be noted in the
example/README.

## 10. Errors, tests, coverage, C4

- **Errors:** unchanged mapping — bad vocabulary/params → `PolicyValidationError` (exit 1);
  unknown referenced CA/mirror name or unreadable cert file → `ConfigError` (exit 3). A missing
  per-kind resolver is an `InternalError` (a registry/resolver wiring bug, not user input).
- **Tests** (`tests/unit/domain/transforms/`): per compiler (assert the exact `Fragment`);
  `validate_transform_steps` (accept the three, reject unknown/malformed); `render` (ordering,
  multi-step, golden Dockerfile); `transform_version` (determinism; sensitivity to params **and**
  resolved values); `schema` (well-formed `oneOf`). App-layer `resolve_ref` keeps its existing
  use-case tests (unknown name / unreadable file → `ConfigError`). Migrate #24's
  `tests/unit/domain/test_transform.py` to the package. **Domain still has no I/O ⇒ no fakes.**
  Coverage gates unchanged (≥ 80 % global, ≥ 90 % `houba.domain`).
- **C4:** no impact — internal refactor, no new actor/external system/integration. (#24 already
  updated `workspace.dsl` for the transform integration.)

## 11. Worked example — adding a step, before vs after

**Today (#24):** add `setTimezone` ⇒ edit `ALLOWED_STEPS`, add an `elif` in
`validate_transform_steps`, add a kwarg + branch in `render_dockerfile`, add it to the
`transform_version` payload, add an `elif` + new field in `_resolve_transform`/`_ResolvedTransform`.

**After this refactor:** add one class in `steps.py`:

```python
class SetTimezone(TransformStepCompiler):
    name = "setTimezone"
    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")
        zone: str = Field(min_length=1)
    def fragment(self, p: "SetTimezone.Params", resources):   # resources == () — no refs
        return Fragment(instructions=(
            f"RUN ln -snf /usr/share/zoneinfo/{p.zone} /etc/localtime && echo {p.zone} > /etc/timezone",
            f"ENV TZ={p.zone}",
        ))
```

…and register it in `BUILTIN_STEPS`. No I/O-layer, schema, validation, render, or version edits —
they are all registry-driven. That delta **is** the deliverable's proof.
