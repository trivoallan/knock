# Command Line Interface

**Usage**:

```console
$ knock [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `reconcile`: Reconcile all MirrorPolicy files under...
* `promote`: Promote staged rebuilds to their...
* `purge`: Reap pending-deletion marks: purge tags...
* `attach`: Ingest a scan report produced upstream and...
* `audit`: Walk the registry and report images that...
* `gc`: Garbage-collect superseded scan-result...
* `verify`: Read knock's facts for a digest and gate...
* `lint`: Validate a policy tree offline and report...
* `version`: Print the CLI version.
* `scan`: Platform scan-pipeline commands (requires...

## `knock reconcile`

Reconcile all MirrorPolicy files under DIRECTORY against their destinations.

**Usage**:

```console
$ knock reconcile [OPTIONS] {directory}
```

**Arguments**:

* `directory`: Directory of MirrorPolicy files (recursive).  [required]

**Options**:

* `--dry-run`: Plan only — no copies, no deletes.
* `-v, --verbose`: Unfold per-operation detail in text output.
* `-j, --concurrency <int range>`: Max parallel tag operations (overrides KNOCK_MAX_CONCURRENCY; 1 = sequential).  [x>=1]
* `--shard-index <int range>`: This shard's 0-based index (pass $JOB_COMPLETION_INDEX in an Indexed Job).  [default: 0; x>=0]
* `--shard-count <int range>`: Total shards N (1 = process all policies).  [default: 1; x>=1]
* `--report-json`: Emit the reconcile report as JSON to stdout (for piping to `knock scan enqueue`).
* `--plan-out <path>`: Gate, step 1: place nothing, write every import/update/rebuild the run would perform to FILE (a ReconcilePlan) for an external evaluator.
* `--apply-plan <path>`: Gate, step 2: reconcile, but apply an import/update/rebuild only if FILE (a filtered ReconcilePlan) still names it; report the others as withheld.
* `--stage-to <str>`: With --apply-plan: push every image the plan orders remediated to this registry (a name from KNOCK_REGISTRIES) instead of its destination, for an external evaluator to judge before `knock promote`. Copies and transform-only rebuilds are placed as usual; without it, an ordered operation is withheld.
* `--staged-out <path>`: With --stage-to: write the remediated images held in staging to FILE (a StagedRebuilds), the input of `knock promote`.
* `--applied-out <path>`: With --apply-plan: write what the run did with each operation to FILE (an AppliedOperations): source digest → digest written, and why an approved operation was withheld.
* `--help`: Show this message and exit.

## `knock promote`

Promote staged rebuilds to their destinations: copy by digest with their evidence,
verify it arrived, then write the tag and the aliases.

**Usage**:

```console
$ knock promote [OPTIONS] {directory}
```

**Arguments**:

* `directory`: Directory of MirrorPolicy files (recursive).  [required]

**Options**:

* `--staged <path>`: A filtered StagedRebuilds file (written by `reconcile --staged-out`): place each entry it still names, and nothing else.  [required]
* `-v, --verbose`: Unfold per-operation detail in text output.
* `-j, --concurrency <int range>`: Max parallel entries (overrides KNOCK_MAX_CONCURRENCY; 1 = sequential).  [x>=1]
* `--report-json`: Emit the report as JSON to stdout.
* `--help`: Show this message and exit.

## `knock purge`

Reap pending-deletion marks: purge tags not seen in prod within the idle window.

**Usage**:

```console
$ knock purge [OPTIONS]
```

**Options**:

* `--registry <str>`: Bound the walk to one registry from the roster.
* `--apply`: Actually delete (default: dry-run, plan only).
* `--help`: Show this message and exit.

## `knock attach`

Ingest a scan report produced upstream and attach it as a stamped OCI referrer.

**Usage**:

```console
$ knock attach [OPTIONS] {image_ref}
```

**Arguments**:

* `image_ref`: Image reference (tag or digest) to stamp.  [required]

**Options**:

* `--report <str>`: Path to the upstream scan report, or '-' for stdin.  [required]
* `--format <str>`: Override report-format auto-detection (e.g. 'sarif').
* `--registry <str>`: Roster entry to authenticate against (overrides ref host-matching).
* `--output <str>`: Output format: 'text' (default) or 'json'.  [default: text]
* `--fail-on <critical|high|medium|low|unknown>`: Exit non-zero if the scan has a finding at or above this severity (CI gate).
* `--help`: Show this message and exit.

## `knock audit`

Walk the registry and report images that do NOT carry knock's provenance stamp.

With KNOCK_LOG_FORMAT=json, stdout is one JSON document: `apiVersion` (knock.io/v1alpha1),
`kind` (CoverageReport), `registries`, `counts`, and `outcomes` — one per image, with
`image_ref`, `digest`, `covered`, `policy`, `signed` (with --signed), `sbom` and
`sbom_formats` (with --sbom: the SBOM formats found, e.g. ["cyclonedx-json", "spdx-json"]),
and `error`. A probe that did not run is null. Within one apiVersion, fields are only added;
a removal, rename or change of meaning bumps it. Schema: docs/reference/schemas/coverage-report.

**Usage**:

```console
$ knock audit [OPTIONS]
```

**Options**:

* `--registry <str>`: Bound the walk to one registry from the roster.
* `--fail-on-uncovered`: Exit non-zero if any image lacks the stamp (CI gate).
* `--signed`: Also probe each stamped image for a signed attestation referrer.
* `--fail-on-unsigned`: Exit non-zero if any stamped image is unsigned (implies --signed).
* `--sbom`: Also probe each stamped image for a package SBOM referrer.
* `--limit <int>`: Stop after N images — bounded smoke-check / walk benchmark over a slice.
* `--help`: Show this message and exit.

## `knock gc`

Garbage-collect superseded scan-result referrers across the registry roster.

**Usage**:

```console
$ knock gc [OPTIONS]
```

**Options**:

* `--registry <str>`: Bound the walk to one registry from the roster.
* `--keep <int>`: Newest scan referrers to retain per (tool, format).  [default: 2]
* `--older-than-days <int>`: Only collect referrers older than this many days.  [default: 30]
* `--apply`: Actually delete (default: dry-run, plan only).
* `--help`: Show this message and exit.

## `knock verify`

Read knock's facts for a digest and gate on them (exit 0 = pass, 1 = fail).

**Usage**:

```console
$ knock verify [OPTIONS] {image_ref}
```

**Arguments**:

* `image_ref`: Image reference (tag or digest) to verify.  [required]

**Options**:

* `--require <str>`: Comma-separated: scan-pass,stamp,sbom,image-signature.  [default: scan-pass]
* `--max-severity <critical|high|medium|low|unknown>`: Fail at or above this scan severity.  [default: high]
* `--max-age <str>`: Scan freshness SLA (e.g. 7d, 12h, 30m).  [default: 7d]
* `--registry <str>`: Roster entry to authenticate against.
* `--output <str>`: Output format: 'text' (default) or 'json'.  [default: text]
* `--help`: Show this message and exit.

## `knock lint`

Validate a policy tree offline and report every problem, not just the first.

Point it at the policies directory, not the repository root. It calls no registry, git
remote or tool. Levels: N1 (each file loads), N2 (steps, ownership and alias overlaps),
N3 (references to the configuration; only when KNOCK_REGISTRIES is set).

With KNOCK_LOG_FORMAT=json, stdout is one JSON document: `apiVersion` (knock.io/v1alpha1),
`kind` (LintReport), `errors`, `warnings` and `skipped`. Schema:
docs/reference/schemas/lint-report.schema.json.
Guide: docs/how-to/lint-policies-in-ci.md.
Exit 0 when there is no error
(warnings do not fail), 1 otherwise, 3 on an invalid directory or configuration.

**Usage**:

```console
$ knock lint [OPTIONS] {directory}
```

**Arguments**:

* `directory`: Policies directory to lint (not the repository root): every .yaml/.yml under it.  [required]

**Options**:

* `--help`: Show this message and exit.

## `knock version`

Print the CLI version.

**Usage**:

```console
$ knock version [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `knock scan`

Platform scan-pipeline commands (requires `pip install knock-oci[scan]`).

**Usage**:

```console
$ knock scan [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `reserve`: Reserve one placed digest from the queue...
* `attach`: Read the reserved digest + the scanner's...
* `enqueue`: Read a reconcile JSON report from stdin...
* `reaper`: Claim idle entries and route...

### `knock scan reserve`

Reserve one placed digest from the queue and write it to /shared for the
scanner + attach steps. Exits 75 (EX_TEMPFAIL) when the queue is empty.

**Usage**:

```console
$ knock scan reserve [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `knock scan attach`

Read the reserved digest + the scanner's SARIF, attach the result, and ack.
A missing/empty SARIF or a transient failure leaves the entry pending (the
reaper retries); a permanent failure dead-letters it.

**Usage**:

```console
$ knock scan attach [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `knock scan enqueue`

Read a reconcile JSON report from stdin and enqueue the placed image refs.

**Usage**:

```console
$ knock scan enqueue [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

### `knock scan reaper`

Claim idle entries and route past-threshold ones to the dead stream.

**Usage**:

```console
$ knock scan reaper [OPTIONS]
```

**Options**:

* `--min-idle-ms <int>`: Idle threshold in ms.  [default: 600000]
* `--max-deliveries <int>`: Dead-letter threshold.  [default: 3]
* `--help`: Show this message and exit.
