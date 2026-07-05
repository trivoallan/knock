# Backstage coverage portal (TechInsights + Dependency-Track) — design

*Status: design (brainstorm capture). Phase 1 = developer-scoped, at the consumption point. Date: 2026-06-17.*
*Researched 2026-06-17: Harbor ≤2.15.x does NOT replicate OCI 1.1 referrers (issue #23210, open) — the
SBOM + signature do not reach team namespaces. The design absorbs it by following the (identical)
digest to the attachment site; everything else is decided.*

## Why

houba stamps `io.houba.*` provenance, carries `owners` as Backstage entity-refs
([multi-owner ownership](2026-06-16-multi-owner-ownership-design.md), ADR 0030), and — on **both the
copy and rebuild paths** since [unify-SBOM-on-syft](2026-06-17-sbom-copy-path-unify-syft-design.md)
(ADR 0034, PR #140) — attaches a package SBOM as a uniform **OCI referrer**
(SPDX *or* CycloneDX via `HOUBA_SBOM_FORMATS`). The thesis is *coverage gates value*: when a CVE
drops, package-level blast-radius is one query. This spec is the **consumption surface** for that
thesis, and the moment the "future Backstage integration" ADR 0030 deferred becomes wired.

The marriage is natural: the **SBOM referrer** feeds **Dependency-Track** (OWASP; the blast-radius
query, productized and free), **ownership** lives in **Backstage**, and houba's stamp is the **join
key**.

## What "dark" actually is here (the corrected model)

Earlier drafts assumed a *replication back door* — a competing path (Harbor replication / `skopeo
sync`) overwriting houba's stamp. **That is wrong for the target org.** The real architecture:

- houba **gates both entry namespaces** — the *official-catalog* project and the *requested*
  (non-catalog) project. Everything external enters through houba and is stamped. So **entry coverage
  is structural (~100 %)**.
- **Replication is internal fan-out**, not a back door: the *requested* project is replicated into
  each **team namespace**, byte-for-byte (Harbor). A byte-for-byte copy is the **same digest** → the
  **stamp annotation survives** the trip. Nothing overwrites it. *There is no flip; the
  realized/declared escape hatch of earlier drafts is removed — it solved a non-problem.*

So what is left uncovered, per consuming service?

1. **Legacy** — images placed before houba existed; unstamped until onboarded. A finite, shrinking
   backlog.
2. **First-party** — a team's *own* built image, pushed straight to its namespace, never through
   houba. **Not houba's domain** → must be excluded from the denominator.

And the fragile thing is **not** the stamp — it is the **referrers**.

## The real fragility: referrer propagation (researched — Harbor ≤2.15.x does NOT replicate them)

The stamp lives in the **manifest annotations** → it rides the digest through replication. But the
**SBOM and the cosign signature are OCI referrers, scoped to the repository they were pushed in**.
When Harbor replicates `requested/foo` → `team-x/foo`, the manifest (and its stamp) is copied, but
whether the **referrers follow is version/config-dependent and currently unknown** for the target
org. So in a team namespace:

- `stamped` (provenance) — **survives** replication. Stable.
- `SBOM present` / `signed` (queryable + verifiable *here*) — **may be lost** if Harbor does not
  replicate accessories.

This is the precise, infra-grounded version of "does coverage stick": not *overwrite*, but
**referrer propagation across the fan-out**.

**Researched 2026-06-17 — the answer is no.** Harbor's replication service does **not** replicate OCI
1.1 referrers (tagless, subject-linked) up to and including the current line (2.14.x, 2.15.0/.1/.2-rc1;
no 2.16 exists) — [issue #23210](https://github.com/goharbor/harbor/issues/23210), open, confirmed on
2.14.1 and 2.15.0. Legacy cosign `.sig` *tag*-based signatures replicate; **OCI 1.1 referrers do not**,
and houba's SBOM (syft referrer) + cosign v3 (OCI 1.1 bundle) are exactly that kind. So in team
namespaces the SBOM + signature are **absent**.

**The design absorbs it without waiting on a Harbor fix** (#23210 has none): the digest is identical
after a byte-for-byte copy, and referrers are addressable by digest wherever they live. So **bar 2 is
computed at the attachment site (the entry namespace) by digest**, not at the consuming team namespace;
the same digest-addressability would make a DT lookup namespace-agnostic too, *if* the org keys DT by
digest — an open question, see §8. The "validation test" below now only confirms the org's exact Harbor
version/config and that the digest-follow resolves.

**The gap is Harbor-specific, not inherent to OCI registries.** Zot's `sync` (stable 2.1.16) *does*
propagate OCI 1.1 referrers — signatures, SBOMs, attestations (`onlySigned` / `syncLegacyCosignTags`
options) — since it is OCI-native and implements the Referrers API. (One caveat irrelevant to houba:
Zot converts upstream *Docker*-format images to OCI on download, changing the digest and dropping
digest-bound signatures unless `preserveDigest: true`; houba already emits OCI, so no conversion.) So
moving the fan-out to Zot mirroring would collapse bar 2 into bar 1 natively — a registry-choice lever,
noted; the target org is on Harbor, so digest-follow stands.

## Design principle: depend on no convention teams must adopt

The org cannot enforce naming/namespace conventions at scale (confirmed). So the portal works off
**signals that already exist** — the stamp, the referrers, `houba audit`, and the Backstage catalog —
plus lightweight per-item human triage. It never requires a team to adopt a path/namespace discipline.

## Decisions

### 1. Developer-scoped, at the *consumption point* (the team namespace); the denominator is a base-chain walk, not a Dockerfile parse

Entry coverage is structural, so the value is where consumption happens: a service's team namespace.
The dependency of interest is the **external base image(s)** the service runs on. We get it **not by
parsing `FROM`** (fragile: ARG, multi-stage, multiple Dockerfiles) but by **reading the
`org.opencontainers.image.base.name` / `.base.digest` annotations** that buildx/BuildKit stamp on every
built image from the final stage's base. These are **manifest annotations → they ride the digest →
they survive Harbor's fan-out** (like the `io.houba` stamp; unlike referrers).

Because the org's golden base images are themselves first-party (built by teams, unstamped), the base
is resolved by **walking the `base.digest` chain** until it terminates:

```
resolve(entity):
  img  = the component's image ref (Backstage catalog — Decision 4 oracle)
  seen = {}                                          # cycle guard
  repeat (cap ~10 hops):
    a = annotations(img)                             # manifest read; rides the digest, survives replication
    if no base.digest in a:           return UNRESOLVED      # scratch / non-buildx hop
    base = a["base.digest"]                          # one hop down
    if base in seen:                  return UNRESOLVED(cycle)
    st = audit_status(base)                          # houba audit, BY DIGEST
    if st.stamped:                    return COVERED(base, st.sbom, st.signed)  # houba vouches → stop
    if is_external(base):             return DARK(base)      # catalog oracle: not first-party → onboard candidate
    img = base                                       # first-party golden base → keep walking
  return UNRESOLVED(depth-cap)
```

> per entity → the resolved external root + status `{covered | dark | unresolved}` · join key = the
> `base.digest` (digest-level, no tag). No `owners` reverse-lookup (you are *on* the entity).

**Stopping conditions:** `stamped` (covered) · `external & unstamped` (dark) · `base.* absent` /
cycle / depth-cap (unresolved). **Dependencies (3, bounded):** the catalog oracle (entity→image +
`is_external`), `houba audit` (coverage by digest), registry annotation reads. Testable in isolation:
feed a fake annotation chain + a fake audit, assert the verdict — one function, no Dockerfile I/O.

No `owners` reverse-lookup (you are *on* the entity); the join key is the **image ref / digest**.

### 2. Replication doesn't strip the stamp — it may strip the referrers → two bars

Because the stamp survives but referrers may not, the card shows **two bars**, meaningful precisely at
the consumption point:

```
Provenance        ████████░░  82%   ← stamped (survives replication; the migration burndown)
Queryable here    ██████░░░░  61%   ← SBOM + signature present in YOUR namespace (can degrade)
```

- **Bar 1 (stamped)** is the stable migration metric: dark (legacy) → onboarded.
- **Bar 2 (referrers present here)** is the steady-state metric: did the SBOM + signature survive the
  fan-out into this namespace. The **gap = replication referrer loss**.
- If the validation test shows Harbor *does* replicate referrers, bar 2 collapses into bar 1 and we
  drop it. Until then, bar 2 is the degradation detector — the hedge, now grounded in referrers, not
  in a phantom overwrite.

Note (#140): SBOM is now on **both** paths, so `stamped ⟹ SBOM-at-source`. The old "copied = no SBOM"
tier is gone; copy-vs-rebuild is now only a **hardening** distinction (internal CA/mirrors), a
secondary dimension, not a queryability tier.

### 3. The surface is a TechInsights FactRetriever (not a live-query plugin)

Scheduled collection → caches registry reads, gives a **trend**, feeds a **check → scorecard badge**.
Fact shape — scalars for the check/trend, a detail array for the card + PR button:

```
fact: houba.provenance.coverage   (per entity, natively timestamped)
  // scalars
  externalDeps, stamped, sbomPresent, signed, dark, unresolved, firstPartyExcluded : integer
  // detail
  images : object   // [{ ref, digest, status, sbom, signed, origin }]
```

- States: `stamped | dark | unresolved`, with `firstPartyExcluded` filtered out of the denominator
  (counted only for transparency). `sbom`/`signed` are per-image referrer sub-states.
- **"What counts as covered" lives in the CHECK, not the fact.** The platform gates on bar 1
  (stamped, stable) and/or bar 2 (referrers here) without re-collecting.
- Native **timestamp** = honest "as of <time>".
- The fact carries **no owners** — the PR button injects the requesting entity-ref at click time.

### 4. Origin (the first-party filter) comes from the Backstage catalog — no convention

Team namespaces **mix** first-party builds and replicated externals, and the stamp only separates
covered from the rest; the *unstamped* set still mixes legacy-dark-external with first-party. With no
registry convention available, the origin oracle is **the Backstage catalog itself**:

- an image that is the **build output of a catalogued component** (it has a source repo, an owner) =
  **first-party** → excluded, automatically, convention-free;
- not a known component output → likely external → `dark` (onboard candidate).

The residue the catalog can't classify falls to **human triage**: the card surfaces the unstamped set
and the dev either **requests onboarding** (external) or **marks first-party** (recorded as a
catalog/Backstage annotation, not a registry convention; remembered thereafter). Second-order effect:
this *incentivizes* cataloguing (register your image, it stops appearing in triage) — a pull, not a
pushed mandate.

### 5. "Onboard" = an idempotent PR that routes the image through the gated entry

A `dark` image is a legacy external not yet flowing through houba. Onboarding adds it to a
`MirrorPolicy` so houba's gated entry stamps it (+ SBOM + signature); Harbor's existing replication
then fans the stamped result into the team namespaces. The button opens a PR against the platform's
**MirrorPolicy repo**:

- **idempotent + aggregating** — one image requested by 20 services ⇒ **one** PR, 20 requesters added
  to `owners`. The aggregation *is* the prioritization signal.
- **destination = the entry namespace** (catalog/requested); replication carries it onward. **No
  "claim the path", no back-door checklist** — replication is houba's distribution mechanism, not a
  competitor.
- `owners` pre-filled with the **requesting entity-ref** (bootstrap — §6). Hardening (copy vs rebuild)
  stays a platform call → the PR is a **well-formed request, not a merge-ready artifact**.
- The one residual gap: **`source` upstream is a `TODO(platform)`** — the internal ref the dev
  consumes does not reliably encode the upstream (`docker.io` vs `quay.io`); the button best-guesses,
  the human confirms.

### 6. `owners` is bootstrap; the usage oracle is the live truth

The `owners` stamp is a **frozen demand-time snapshot** on the digest, not a maintained registry. The
**first** PR seeds it; thereafter the **usage oracle** answers live blast-radius ("who pulls X now?")
and purge. A 2nd consumer of an already-covered image produces **no PR** — they appear because they
pull. Boundary: **the `base.*` annotation = declared build-time base** (the dev card); **usage oracle = what runs** (org-wide,
phase 2). One houba-side consequence: the `UsageOraclePort` widens from "is X still pulled?" to "who
pulls X?".

### 7. The portal consumes `houba audit` — it does not re-walk the registry

`houba audit` is the **supply-side** record: it walks the registry (including team namespaces) and
classifies each digest. The FactRetriever adds only the **demand-side** denominator (the base-chain
walk of Decision 1) and joins. Consequences:

- **No registry credentials in Backstage**; no registry logic re-implemented in TypeScript.
- **Bar 2 is probed at the attachment site, by digest — not per consuming namespace.** Since Harbor
  ≤2.15.x does not replicate OCI 1.1 referrers (researched, #23210), a naïve per-team-ns probe would
  report *everything* unsigned / no-SBOM (false negative). The referrers live where houba attached
  them (the entry namespace); the digest is identical after replication, so `audit --signed` (+ a
  cheap `--sbom` tier, #140) over the **entry** namespaces is the signal, and a team-ns image inherits
  its digest's status.
- **houba-side asks (investigated 2026-06-17):** `houba audit` already emits a machine-consumable
  `CoverageReport` (Pydantic + published JSON Schema, JSON under `HOUBA_LOG_FORMAT=json`,
  per-image `covered`/`signed`/`policy`). The gaps: (1) outcomes are **tag-keyed, no `digest`** — add
  `digest` to `CoverageOutcome` (the join key; the regctl adapter already resolves it); (2) an
  **`--sbom` referrer tier** for bar 2. Both small.

### 8. Dependency-Track is a deep-link, not an embedded card — and houba does not decide DT's keying

The vuln surface splits by *plane*, not by audience: **DT computes the vuln posture; Backstage presents
coverage.** Both planes have human users — the **owner** (proactive, per-service → the Backstage card)
and the **incident responder** (reactive, org-wide → DT's own frontend). So:

- **No embedded DT card, no findings API in Backstage.** When the owner asks "and is it vulnerable?",
  the coverage card **deep-links by digest to DT's own frontend** (which the org already deploys —
  `dependency-track-frontend`). DT's UI is the responder's surface; we link to it, we do not
  re-implement it. This keeps Decision 3 intact (no per-image DT call at collection) and keeps both
  registry **and** DT credentials off the FactRetriever path.
- **houba does not decide DT's project keying.** By its own boundary (ADR 0032; no HTTP layer) houba
  **never writes to DT**, so it has no standing to make `version = <digest>` true — whoever owns the
  org's DT *ingestion* (a CI push or a DT registry-pull) picks the key. houba's only contribution is to
  **emit the digest as a stable join key** (the §7 `digest`-on-`CoverageOutcome` ask); the resolver
  (Decision 1) already yields the external base digest the link is built from.
- **OPEN — the org's DT taxonomy is undecided (confirmed 2026-06-17), and DT is greenfield with no
  ingestion owner yet.** This section therefore captures intent, it does not commit a join. Two unknowns
  gate it, neither houba's to resolve: *who owns ingestion*, and *how DT addresses a project*. The
  cheapest next check (≈30 min on the org instance): **does DT's frontend route a URL by `name`+`version`
  (or by search), or only by internal project UUID (`/projects/{uuid}`)?** If the latter, the deep-link
  needs one **read-only** `GET /api/v1/project/lookup?name=&version=` to resolve the UUID — so clic-through
  costs "1 lookup + 1 read-only token", not zero. That answer plus the keying decision become their own
  spec; nothing here blocks shipping the coverage portal (Decisions 1–7).
- **Graceful degradation + still not houba's job to load.** Until ingestion exists, the deep-link
  resolves to *"no DT project for this digest"* — honest, reactive, and it lights up the day the org
  wires ingestion. **Loading the SBOM into DT remains out of houba's scope** (same stance as `attach`);
  #140 already emits CycloneDX natively (`HOUBA_SBOM_FORMATS`), DT's first-class format, so the format
  gap is closed when someone does build that ingestion.

## Edge cases of the base-chain walk (replaces the old "parsing FROM" gotcha)

There is **no Dockerfile parser** — the whole `FROM`/ARG/multi-stage/multi-file gotcha is dissolved by
reading the resolved `base.*` annotation (Decision 1). What remains are the walk's edges:

- **multi-arch index** — read `base.*` at the index level (else any platform manifest; normally the
  same base). `ponytail:` index-level, ceiling noted.
- **`base.digest` points to a GC'd / unreachable manifest** → `unresolved`.
- **chain is 100 % first-party and never carries `base.*`** (a non-buildx hop, or `FROM scratch`) →
  `unresolved` at the missing-annotation hop.
- **cycle / depth-cap** → `unresolved`, logged.

Load-bearing assumption to spot-check (like the Harbor test): every hop is buildx/BuildKit-built, so it
carries `base.*`. A hop without it → `unresolved` there; the fix/incentive is to build golden bases
with buildx, or route them through houba (which stamps `base.*`).

## The validation test — researched (Harbor ≤2.15.x doesn't replicate referrers); confirm + digest-follow

The headline question is **answered by research**: Harbor's replication service does not carry OCI 1.1
referrers, so the SBOM + signature are absent in team namespaces
([#23210](https://github.com/goharbor/harbor/issues/23210), open; confirmed 2.14.1 + 2.15.0; no 2.16
exists). What remains is to confirm the org's exact version/config and that the **digest-follow**
resolves. Cheapest check against the real instance:

1. Onboard one image so houba stamps it **and** attaches SBOM + signature referrers in the entry ns.
2. Let Harbor replicate it into a team namespace.
3. At the **team-ns** ref: stamp annotation present (expect yes); referrers present (expect **no**).
   Then probe the **same digest in the entry ns**: referrers present (expect yes) — the path bar 2 / DT
   actually use.

- Matches the research (team-ns no, entry-ns yes) → compute bar 2 at the entry by digest; ship it.
- Referrers *do* follow (a future Harbor, or accessory replication configured) → bar 2 == bar 1; drop
  bar 2, the card is a pure migration burndown.

`scripts/stick-test.sh` demonstrates the mechanism locally (referrers are repo-scoped: a manifest-only
copy loses them, `--referrers` keeps them) — the two branches above.

## Out of scope / deferred

- **`copied → rebuild` "request hardening" PR** — phase 2 (hardening is now a secondary dimension, not
  queryability).
- **Org-wide security-engineer view** — phase 2; needs the usage oracle (enumerate consumers) and
  re-activates the `owners` reverse-lookup.
- **Cryptographic verification** of stamp/signature — trusts referrer presence, same ceiling as
  `reconcile` / `audit --signed`.
- **How the SBOM reaches Dependency-Track** — CI push or DT registry-pull; out of houba's scope (§8).

## Docs to sync (same change)

- ADR mirror: `docs/architecture/decisions/0035-backstage-coverage-portal.md` (0034 is taken by the
  merged unify-SBOM-on-syft ADR), linking this spec.
- C4 `workspace.dsl`: adds `backstage` + `dependencyTrack` (External/Downstream) + relationships;
  Landscape/Context use `include *`. **Pending:** regenerate `docs/architecture/_export/*.mmd` (no
  Make target / CI drift-check today).
- `docs/architecture/design.md`: Backstage + Dependency-Track as downstream consumers of the stamp /
  referrers.
- `docs/examples/`: **deferred** — the plugin is TypeScript outside the houba repo, no `MirrorPolicy`
  field changes. houba-side surface = the small asks in §7 (`digest` on `CoverageOutcome`, `--sbom`
  audit tier) + the phase-2 `UsageOraclePort` widening.
- Roadmap: a *Later*/consumption-layer bet, downstream of the delivered mandate.

## Appendix — onboard PR body template (the named deliverable, Decision 5)

`{{…}}` are values the button fills. Title: `onboard: {{repo}}:{{tag}} — route through houba`.

```markdown
**Requested via Backstage** by `{{requesting_entity}}`.

`{{repo}}:{{tag}}` is consumed but carries no `io.houba` stamp (legacy — it predates houba's gate, or
was never routed through it). This PR routes it through houba's gated entry so it is stamped + gets an
SBOM + signature, then replicates into the team namespaces like everything else.

### Add to the MirrorPolicy (scaffolded; review before merge)
```yaml
source:
  registry: {{upstream_registry_guess}}   # TODO(platform): confirm upstream — not encoded in the internal ref
  repository: {{repo}}
imports:
  - name: {{repo_leaf}}
    owners:
      - {{requesting_entity}}              # bootstrap; more requesters appended below
    tags:
      includeRegex: "^{{tag_escaped}}$"    # the tag {{requesting_entity}} consumes; widen if needed
    destinations:
      - project: {{entry_project}}         # the gated entry (catalog/requested); replication fans out
        repository: {{repo}}
```
Platform decisions:
- [ ] confirm upstream source (`{{upstream_registry_guess}}/{{repo}}` assumed)
- [ ] copy or rebuild? both get an SBOM (#140); **rebuild** additionally hardens (internal CA/mirrors).

### Requesters (bootstrap owners — appended idempotently, not new PRs)
- {{requesting_entity}}
```

Template design notes:
1. **`destination = the gated entry`, not the team namespace.** houba stamps once at the entry;
   Harbor's existing replication carries the stamped result onward. No path-claiming, no back-door
   checklist — replication is the distribution mechanism, not a competitor.
2. **`source` is a `TODO(platform)`.** The internal ref doesn't reliably encode the upstream; the
   button best-guesses, the human confirms.
3. **Copy vs rebuild is now a hardening choice, not a queryability one** (#140 gave both an SBOM).
