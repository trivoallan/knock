# Team folder example — two teams, two kargo gates

A folder of MirrorPolicies, one per team, each with its own `owners` (Backstage entity-ref) and
its own destination repo. Two teams here:

- **team-platform** (`group:default/platform`) → a clean `debian:bookworm-slim` placed to
  `platform/debian`. Promotes cleanly through its kargo gate.
- **team-data** (`group:default/data`) → the backdoored `debian-xz` (CVE-2024-3094) placed to
  `data/debian-xz`. Held by its kargo gate (critical scan finding).

Run it: `make demo-teams` (needs a `make demo` cluster up). See the demo-teams how-to.
