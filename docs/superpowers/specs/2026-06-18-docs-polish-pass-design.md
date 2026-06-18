# Docs polish pass — raise the self-serve surface

*Spec — 2026-06-18. Implements the **"Docs polish pass"** item of the Now / adoption
section of [docs/roadmap.md](../../roadmap.md). Scope is **documentation only**: no
software-architecture change, no schema change, no new actor/external system/integration.*

## Why

The docs site is live and Diátaxis-complete (tutorials / how-to / explanation / reference,
Docusaurus sourcing `docs/`). The roadmap's adoption frontier needs the self-serve surface to be
good enough to onboard a target org *without us*. Four quality gaps remain:

1. The architecture story (the hexagon, the two paths, why the stamp *is* the product) lives only
   in `docs/architecture/` — **excluded from the published site**. A self-serve reader never sees it.
2. The Mermaid theme is enabled but **no diagram renders on the published site**.
3. Most example policies are **YAML-only**, with no worked prose.
4. One explanation page (`sbom.md`) is **prose-only** — the only real gap in code-block coverage
   (everything else is already fenced).

## Decisions (settled in brainstorming)

| Topic | Decision |
|---|---|
| Architecture presentation | **Two artifacts**: a published narrative page **and** a slidev deck. |
| Diagrams | **Hand-authored narrative diagrams only.** The committed Structurizr C4 exports stay **linked, never embedded** (they are auto-generated, verbose, and resync on every DSL change — copying them inline is sync debt). |
| Examples | **Consolidate into how-to / explanation guides** — no per-example READMEs (that would violate Diátaxis; `examples/` is the runnable catalog). |
| Code blocks | Mostly done; fix `sbom.md` + quick sweep. |

## Scope — five workstreams

### 1. Architecture narrative page — `docs/explanation/architecture.md`

A new published Explanation page (wired into the Explanation sidebar). It **tells the story** of the
hexagon: who uses houba and what it talks to (the scene), why the layering is load-bearing, the two
paths (copy / rebuild), and why the stamp + SBOM *is* the product. It is **not** a copy of
`design.md`. `design.md` and the full Structurizr C4 model remain the GitHub deep-dive, linked at the
foot of the page for depth. Single source preserved: the page narrates; `design.md` stays
authoritative for rationale.

### 2. Narrative diagrams — 4, hand-authored, shared page + deck

All hand-authored Mermaid (not Structurizr exports), in narrative order:

1. **Landscape light** — the scene: actors (platform/security engineer, app team) + external systems
   (source/destination registries, BuildKit, signer, scanner, usage oracle, consumers) around houba.
   A simplified, readable redraw of the C4 Context — *not* the verbose export.
2. **Hexagon** — internal structure. **Reuse the existing clean flowchart in `design.md`** (it is
   already hand-authored), trimmed for the narrative.
3. **Copy vs rebuild** — the two placement paths.
4. **Stamp + SBOM + referrer** — the payoff: how the label and the SBOM turn a CVE into a
   blast-radius query at incident time.

The committed Structurizr C4 `.mmd` exports remain **linked only**. No `workspace.dsl` change: these
diagrams are a narrative redraw of the *existing* model, not a model change, so the C4-sync rule does
not trigger.

### 3. Slidev deck — `presentation/` (repo root)

A narrative deck (~12–15 slides) derived from the page, reusing the 4 Mermaid diagrams (slidev
renders Mermaid natively). Standalone slidev project (own `package.json`), **outside `docs/`** so
Docusaurus does not pick it up as a page. **Build local-on-demand, not wired to CI** — the deck is a
talk artifact, not published automatically.

`ponytail:` slidev pulls in a Node toolchain. Kept as an isolated project; promote to a CI build only
if/when the deck needs to be published — not now.

### 4. Examples consolidated into guides

`examples/` stays the runnable MirrorPolicy catalog; the worked prose moves to the right Diátaxis mode:

- **`hardened` + `attested`** (rebuild path — *no how-to exists today*) → a **new how-to**,
  `docs/how-to/rebuild-and-harden.md`, walking the rebuild path (transforms: CA inject + package
  mirrors) and signed attestations, using those two policies as the worked cases.
- **`retention`** → folded into the existing `docs/explanation/deletion-and-retention.md`.
- `docs/examples/README.md` stays the catalog index. No per-example README files.

### 5. Code blocks

`docs/explanation/sbom.md` (prose-only) gets fenced, runnable snippets (the syft/SBOM commands and a
referrer-inspect example). Quick sweep of the other published pages for any stray inline command;
fence what's found. Small lot.

## Out of scope (explicit)

- **Schema rendering** (the `anyOf > item N` noise in the generated reference) — a distinct roadmap
  item flagged *carries risk*; separate work.
- **`audit --fail-on-no-sbom`** — a feature, not docs polish.
- Any `workspace.dsl` / C4 model change, any `make reference` regeneration (no schema touched).

## Verification

- `cd website && npm run build` passes (Docusaurus `onBrokenLinks` fails the build on dead links —
  this is the link check; the new page + new how-to must resolve).
- All 4 Mermaid diagrams render (build catches syntax errors).
- Slidev deck parses/builds (`npx slidev build presentation/slides.md` or equivalent).
- Diátaxis integrity: the new page is pure explanation, the new how-to is pure task — no conflation.
- Coverage gates (pytest) untouched — no code change.

## Deliverables checklist

- [ ] `docs/explanation/architecture.md` (+ sidebar/category wiring)
- [ ] 4 hand-authored Mermaid diagrams (landscape-light, hexagon, copy-vs-rebuild, stamp+SBOM+referrer)
- [ ] `presentation/` slidev project (deck reusing the diagrams)
- [ ] `docs/how-to/rebuild-and-harden.md` (hardened + attested examples worked in)
- [ ] `retention` worked into `docs/explanation/deletion-and-retention.md`
- [ ] `docs/explanation/sbom.md` code blocks + sweep
- [ ] Thin ADR under `docs/architecture/decisions/` recording the docs-presentation decisions
      (published narrative page + deck; hand-authored diagrams over embedded C4 exports;
      examples-into-guides) — per the repo's spec-mirrors-an-ADR convention.
