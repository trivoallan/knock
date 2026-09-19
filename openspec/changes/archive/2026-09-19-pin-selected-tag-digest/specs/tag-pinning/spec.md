## ADDED Requirements

### Requirement: A selected tag can be pinned to the digest expected for it

`MirrorPolicy` imports SHALL accept `tags.pins`, a map from tag name to an OCI digest
(`sha256:<64 hex>` or `sha512:<128 hex>`). A malformed digest SHALL fail policy validation. A pin
SHALL NOT select a tag; selection stays with `includeRegex`, `excludeRegex`, `semverOnly` and
`names`.

#### Scenario: Malformed pin

- **WHEN** a policy declares `pins: {"7.2.5": "latest"}`
- **THEN** loading the policy fails with a validation error

#### Scenario: A pin does not select

- **WHEN** `pins` names a tag that `names` and the regex filters do not select
- **THEN** the tag is not planned and the pin has no effect

### Requirement: A pinned tag whose upstream digest moved is withheld, not placed

When a selected tag is pinned and its upstream digest differs from the pin, the reconcile SHALL NOT
import, update, sign or attach an SBOM to that tag for the run. It SHALL keep the tag in the desired
set, so an existing mirror tag is neither deleted nor marked. It SHALL NOT re-point an alias whose
target is that tag. It SHALL report a `pin_mismatch` operation that carries the observed digest and
the pinned digest, and count it in `totals.pin_mismatch` at every report level. A pin mismatch
SHALL NOT be an error: it changes neither the run status nor the exit code.

#### Scenario: First import against a moved tag

- **WHEN** `7.2.5` is pinned to `sha256:aaa…`, upstream serves `sha256:bbb…`, and the mirror has no `7.2.5`
- **THEN** nothing is copied, annotated or signed, and the report counts one `pin_mismatch` for `7.2.5`

#### Scenario: Placed tag, upstream moved

- **WHEN** the mirror already holds `7.2.5` and upstream moved away from the pin
- **THEN** the mirror's `7.2.5` is neither updated, re-signed nor deleted

#### Scenario: Run exit code

- **WHEN** the only noteworthy outcome of a run is a `pin_mismatch`
- **THEN** `knock reconcile` exits 0 with `status=ok`, and the text recap shows `pin_mismatch=1`

### Requirement: A matching pin supersedes the stability window

When a selected tag is pinned and its upstream digest equals the pin, the reconcile SHALL treat a
mirror whose recorded base digest differs from the pin as out of date and update it immediately,
regardless of the digest-stability window.

#### Scenario: Pin matches a freshly moved tag

- **WHEN** upstream moved `7.2.5` to the pinned digest one day ago and the mirror still holds the old base
- **THEN** the tag is updated in this run

### Requirement: Unpinned selection is unchanged

A selected tag without a pin SHALL be reconciled exactly as before this change.

#### Scenario: No pins

- **WHEN** a policy declares no `pins`
- **THEN** the plan and the report match those of the same policy before this change
