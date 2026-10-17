# Lint a policy repository in CI

**`knock lint`** validates a whole tree of MirrorPolicy files, offline, and reports every problem
it finds instead of stopping at the first one. Run it in the merge-request job of the repository
that holds your policies, so a broken policy is refused at review time and not at the next
`knock reconcile`.

It is **read-only** and calls no registry, git remote, builder or signer. It needs only the
policy files, so it runs on any CI runner that has knock.

```bash
uv run knock lint policies/
```

## Point it at the policies directory

Pass the directory that holds the policies, not the repository root. `knock lint` reads every
`.yaml` and `.yml` file under the directory, recursively, as a MirrorPolicy. At the repository root,
that would pick up your CI configuration (`.gitlab-ci.yml`, `.github/workflows/*.yml`) and report it as an invalid
policy. Files that are not YAML, such as a `README.md`, are never read.

A directory that does not exist (or is a file) exits 3. A directory with no `.yaml` or `.yml` file
reports an error and exits 1, so a mistyped path cannot pass the job by finding nothing.

## What it checks

| Level | Needs configuration | What it catches |
|---|---|---|
| **N1** | no | Each file loads as `knock reconcile` loads it: well-formed YAML, the right `apiVersion` and `kind`, no unknown field, and every rule of the model. |
| **N2** | no | The tree as a whole. Each import resolves against its `defaults`. Every `transform` and `remediate` step is a registered step with valid parameters. Each destination repository belongs to one policy, the same rule `reconcile` enforces. Imports of one policy do not write the same alias into the same repository. |
| **N3** | yes | The references a policy makes to the configuration: the destination registry, each `caCert` and each package mirror. |

N1 and N2 report every error across the tree in one run. Each finding carries the file path
(relative to the directory you passed), the location inside the policy when one is known, and a
message.

### Alias overlaps

An alias is *literal* when it has no `{…}` placeholder, such as `latest`. Within one policy:

- Two imports that write the same literal alias into the same repository are an **error**.
- Two imports that write alias templates (such as `{major}`) into the same repository are a
  **warning**, because whether they collide depends on upstream tags that `knock lint` does not read.

Warnings do not fail the job. Imports of *different* policies are not compared for aliases:
sharing a repository is already an ownership error.

## What N3 needs

N3 runs only when `KNOCK_REGISTRIES` is set, the same JSON map that `knock reconcile` reads (see
[Install and configure knock](install-and-configure.md)). Set `KNOCK_TRANSFORM_CA_CERTS` and
`KNOCK_TRANSFORM_PACKAGE_MIRRORS` as well if your policies reference CAs or package mirrors by name.
CA files must be readable from the CI job: N3 reports an error for each CA file it cannot read.

With `KNOCK_REGISTRIES` set, an unknown name is an error:

```text
ERROR redis.yaml: unknown registry 'quay'; configured: ['harbor']
```

Without `KNOCK_REGISTRIES`, N3 is **skipped**, and the skip does not fail the job. The report says so
on its first line (text) or in `skipped` (JSON), so you can tell a green run that checked the
configuration from one that did not:

```text
skipped: N3 (KNOCK_REGISTRIES not set)
```

Setting `KNOCK_REGISTRIES` also changes how destinations are compared. With it, a repository is
identified by its resolved registry host, project and repository. Without it, by the logical registry
name, project and repository.

## Add the job to CI

Set `KNOCK_LOG_FORMAT=json` for a machine-readable report on stdout; leave it unset for text.
This GitLab CI job runs on merge requests that touch the policies directory, using the published
image described in [Install and configure knock](install-and-configure.md):

```yaml
lint-policies:
  image:
    name: ghcr.io/trivoallan/knock:<version>
    entrypoint: [""]
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes: ["policies/**/*"]
  variables:
    KNOCK_LOG_FORMAT: json
  script:
    - knock lint policies/ | tee lint-report.json
  artifacts:
    when: always
    paths: [lint-report.json]
```

In GitHub Actions, run the same `knock lint policies/` command as a step of a `pull_request` job
that uses the same image, or the package installed as in the install guide.

To make N3 run, add `KNOCK_REGISTRIES` to the job's variables.

## Exit codes and the JSON report

| Exit | Meaning |
|---|---|
| 0 | No error. Warnings and skipped levels do not fail. |
| 1 | At least one error. |
| 3 | The directory is invalid, or the configuration (such as `KNOCK_REGISTRIES`) cannot be read. |

With `KNOCK_LOG_FORMAT=json`, stdout is one JSON document. For a tree with a repeated literal alias,
a repository owned by two policies, and overlapping templates:

```json
{"apiVersion":"knock.io/v1alpha1","kind":"LintReport","errors":[{"level":"N2","path":"nginx.yaml","loc":null,"message":"alias 'latest' is written into 'harbor/lib/nginx' by imports[0] 'v1' and imports[1] 'v2'","related":[]},{"level":"N2","path":"nginx.yaml","loc":null,"message":"destination repository 'harbor/lib/nginx' is written by policies 'nginx' (nginx.yaml) and 'other' (other.yaml); a repository must be owned by exactly one policy","related":["other.yaml"]}],"warnings":[{"level":"N2","path":"nginx.yaml","loc":null,"message":"alias templates '{major} / {major}' written into 'harbor/lib/nginx' by imports[2] 'v3' and imports[3] 'v4' may collide, depending on upstream tags","related":[]}],"skipped":[{"level":"N3","reason":"KNOCK_REGISTRIES not set"}]}
```

The text output of the same run:

```text
skipped: N3 (KNOCK_REGISTRIES not set)
ERROR nginx.yaml: alias 'latest' is written into 'harbor/lib/nginx' by imports[0] 'v1' and imports[1] 'v2'
ERROR nginx.yaml: destination repository 'harbor/lib/nginx' is written by policies 'nginx' (nginx.yaml) and 'other' (other.yaml); a repository must be owned by exactly one policy (also: other.yaml)
WARN nginx.yaml: alias templates '{major} / {major}' written into 'harbor/lib/nginx' by imports[2] 'v3' and imports[3] 'v4' may collide, depending on upstream tags
lint  errors=2 warnings=1
```

The document is versioned (`apiVersion: knock.io/v1alpha1`); its contract is the published
[lint report schema](../reference/schemas/lint-report.md).

## What it does not catch

Collisions are judged offline, from the policy files alone, so some are out of reach:

- A template and a literal that could meet (`{major}` and `1`) are not compared.
- Two variants of one import with the same suffix that write the same alias are not reported.
- A destination listed twice in one import is not reported.
- Without `KNOCK_REGISTRIES`, two different registry names that point at the same host are not
  matched. Set it to compare resolved hosts.

None of these is a hole in the gate. **`knock reconcile` stays the backstop**: it still stops at the
first invalid policy and refuses these collisions before it mutates anything. `knock lint` moves the
feedback earlier and reports everything at once; it does not replace that check.
