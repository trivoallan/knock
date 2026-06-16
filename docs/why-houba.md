# Why houba

## 2 a.m. A critical CVE drops.

There is only one question that matters in the next hour:

> **What's our blast radius — and who owns it?**

Which of the images you run are affected, where are they, and whose pager
should be going off. Every minute you spend *assembling* that answer is a
minute the vulnerability is live.

## You probably can't answer it today

You may already scan everything — Trivy in CI, a registry scanner, a vendor
dashboard. That tells you the CVEs inside *one image at a time*. It does not
tell you, across your whole fleet, *which images carry the affected component
and who is on the hook for them* — not in one query, because:

- External images came in through several paths (a `docker pull` here, a
  mirror there, a base image three layers down), so there is no single place
  that knows what entered.
- They were scanned in different formats, at different times, by different
  tools — the signal isn't uniform, portable, or comparable.
- Nothing records **ownership** on the image itself, so "whose is this?"
  is a Slack archaeology dig.

So the answer becomes a frantic spreadsheet. At 2 a.m.

## The problem was never *getting images in*

Mirroring solved that years ago. `skopeo sync` and Harbor replication copy
images byte-for-byte and do it well. The problem is that images arrive with
**no consistent, queryable, portable provenance** — so at incident time you
have bytes, but no answers.

houba is **not** another mirror. It is a **stamper**: a single front door
through which every external image passes, gets hardened where you ask (internal
CAs, internal package mirrors), and — always — gets stamped with the *same*
standardized provenance and a signed attestation.

## The bet: one front door, one query

Because every image that entered came through houba and carries the *identical*
stamp, the 2 a.m. question collapses into **one query in the observability stack
you already run** — Datadog, Wiz, PowerBI, whatever reads OCI annotations. houba
produces the stamp; your tools answer the question.

## The proof is the label

This is what houba writes onto every image. No magic, no houba-only database —
just annotations any scanner already reads:

```console
$ regctl manifest get registry.example.com/redis:7.2 --format '{{ jsonPretty .Annotations }}'
{
  "org.opencontainers.image.source":      "docker.io/library/redis",
  "org.opencontainers.image.revision":    "9d8e4ef...",
  "org.opencontainers.image.base.name":   "docker.io/library/redis:7.2",
  "org.opencontainers.image.base.digest": "sha256:1f3c...",
  "org.opencontainers.image.created":     "2026-06-16T01:53:00Z",
  "io.houba.artifact.type":               "derived",
  "io.houba.policy":                      "datastores",
  "io.houba.import":                      "redis",
  "io.houba.variant":                     "hardened",
  "io.houba.owners":                      "group:platform-data,group:sre",
  "io.houba.transform.steps":             "injectCA,rewritePackageSources",
  "io.houba.transform.version":           "3"
}
```

The blast-radius query is now boring: *"every image whose
`org.opencontainers.image.base.digest` is `sha256:1f3c…`, grouped by
`io.houba.owners`."* One line. The owners field tells you who to page.

## The catch — and we'll say it plainly

A stamp on 40 % of your fleet is **useless** in an incident: the blind spots
are exactly where the next vulnerability hides. houba's value is proportional
to it being the **mandatory** path for external images. Adopting houba means
making it the single front door, not one option among several.

That is a real ask. We think it's the right one — a blast-radius answer you
can only half-trust is not an answer.

## Why this is safe to mandate

You are not betting on houba the tool. You are adopting a **label**, and the
label is built from **OCI-standard annotation keys** — the same
`org.opencontainers.image.*` fields the ecosystem already standardized. Any
scanner, registry, or policy engine reads them for free; the houba-specific
facts live under a prefix you choose (`io.houba.*`, or none at all).

So the exit cost is near zero: **if houba disappears tomorrow, every image you
already stamped stays exactly as readable.** The provenance is portable by
construction, not locked inside a product. The label *is* the product — and it
outlives the tool that wrote it.

---

*Convinced, or want to see it run? → [Getting started](../README.md#quick-start)
· [Example policies](examples/README.md) · [The provenance contract](architecture/design.md)*
