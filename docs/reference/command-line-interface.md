---
sidebar_position: 3
---

# Command Line Interface

**Usage**:

```console
$ houba [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `reconcile`: Reconcile all MirrorPolicy files under...
* `purge`: Reap pending-deletion marks: purge tags...
* `attach`: Ingest a scan report produced upstream and...
* `audit`: Walk the registry and report images that...
* `gc`: Garbage-collect superseded scan-result...
* `verify`: Read houba's facts for a digest and gate...
* `version`: Print the CLI version.

## `houba reconcile`

Reconcile all MirrorPolicy files under DIRECTORY against their destinations.

**Usage**:

```console
$ houba reconcile [OPTIONS] DIRECTORY
```

**Arguments**:

* `DIRECTORY`: Directory of MirrorPolicy files (recursive).  [required]

**Options**:

* `--dry-run`: Plan only — no copies, no deletes.
* `-v, --verbose`: Unfold per-operation detail in text output.
* `-j, --concurrency INTEGER RANGE`: Max parallel tag operations (overrides HOUBA_MAX_CONCURRENCY; 1 = sequential).  [x>=1]
* `--shard-index INTEGER RANGE`: This shard's 0-based index (pass $JOB_COMPLETION_INDEX in an Indexed Job).  [default: 0; x>=0]
* `--shard-count INTEGER RANGE`: Total shards N (1 = process all policies).  [default: 1; x>=1]
* `--help`: Show this message and exit.

## `houba purge`

Reap pending-deletion marks: purge tags not seen in prod within the idle window.

**Usage**:

```console
$ houba purge [OPTIONS]
```

**Options**:

* `--registry TEXT`: Bound the walk to one registry from the roster.
* `--apply`: Actually delete (default: dry-run, plan only).
* `--help`: Show this message and exit.

## `houba attach`

Ingest a scan report produced upstream and attach it as a stamped OCI referrer.

**Usage**:

```console
$ houba attach [OPTIONS] IMAGE_REF
```

**Arguments**:

* `IMAGE_REF`: Image reference (tag or digest) to stamp.  [required]

**Options**:

* `--report TEXT`: Path to the upstream scan report, or '-' for stdin.  [required]
* `--format TEXT`: Override report-format auto-detection (e.g. 'sarif').
* `--registry TEXT`: Roster entry to authenticate against (overrides ref host-matching).
* `--output TEXT`: Output format: 'text' (default) or 'json'.  [default: text]
* `--fail-on [critical|high|medium|low|unknown]`: Exit non-zero if the scan has a finding at or above this severity (CI gate).
* `--help`: Show this message and exit.

## `houba audit`

Walk the registry and report images that do NOT carry houba's provenance stamp.

**Usage**:

```console
$ houba audit [OPTIONS]
```

**Options**:

* `--registry TEXT`: Bound the walk to one registry from the roster.
* `--fail-on-uncovered`: Exit non-zero if any image lacks the stamp (CI gate).
* `--signed`: Also probe each stamped image for a signed attestation referrer.
* `--fail-on-unsigned`: Exit non-zero if any stamped image is unsigned (implies --signed).
* `--sbom`: Also probe each stamped image for a package SBOM referrer.
* `--help`: Show this message and exit.

## `houba gc`

Garbage-collect superseded scan-result referrers across the registry roster.

**Usage**:

```console
$ houba gc [OPTIONS]
```

**Options**:

* `--registry TEXT`: Bound the walk to one registry from the roster.
* `--keep INTEGER`: Newest scan referrers to retain per (tool, format).  [default: 2]
* `--older-than-days INTEGER`: Only collect referrers older than this many days.  [default: 30]
* `--apply`: Actually delete (default: dry-run, plan only).
* `--help`: Show this message and exit.

## `houba verify`

Read houba's facts for a digest and gate on them (exit 0 = pass, 1 = fail).

**Usage**:

```console
$ houba verify [OPTIONS] IMAGE_REF
```

**Arguments**:

* `IMAGE_REF`: Image reference (tag or digest) to verify.  [required]

**Options**:

* `--require TEXT`: Comma-separated: scan-pass,stamp,sbom.  [default: scan-pass]
* `--max-severity [critical|high|medium|low|unknown]`: Fail at or above this scan severity.  [default: high]
* `--max-age TEXT`: Scan freshness SLA (e.g. 7d, 12h, 30m).  [default: 7d]
* `--registry TEXT`: Roster entry to authenticate against.
* `--output TEXT`: Output format: 'text' (default) or 'json'.  [default: text]
* `--help`: Show this message and exit.

## `houba version`

Print the CLI version.

**Usage**:

```console
$ houba version [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.
