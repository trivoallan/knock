# 12. Delegated tag deletion

Date: 2026-06-12

## Status

Accepted

Extends [3. Reconcile output contract](0003-reconcile-output-contract.md)

## Context

When a tag falls out of a policy, houba hard-deleted it immediately. But houba has no
visibility into what is deployed; a tag that left the policy may still run in production,
and removing it can break a live pull-by-tag. The authority that knows prod usage is an
external system, not houba.

## Decision

Add a deletionMode resolved through a most-specific-wins cascade (policy → destination →
global, default purge). In `mark` mode, houba attaches a `pending-deletion` OCI referrer
(`application/vnd.houba.lifecycle.pending+json`) instead of deleting: the image digest stays
immutable and the tag stays pullable. An external reaper discovers candidates via the
referrers API and owns the purge. Marks are auto-cleared when a tag re-enters the policy.

## Consequences

houba stays a signal emitter for delegated deletion; `purge` mode is unchanged and remains
the default. A new external actor (the reaper) appears in the C4 model. RegistryPort gains
referrer list/put/delete.

Full design spec: [2026-06-12-delegated-tag-deletion-design.md](../../superpowers/specs/2026-06-12-delegated-tag-deletion-design.md)
