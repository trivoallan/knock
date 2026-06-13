workspace "houba" "Single front door / stamper for external container images." {

    # houba is the subject of the Context / Container / Component / Deployment views — always
    # drawn as the boundary, never as a plain element — so the "element not on any view"
    # inspection false-positives on it (it does render as a box in the Landscape view).
    # Downgrade just that one inspection; every other inspection stays a hard CI gate.
    properties {
        "structurizr.inspection.model.element.noview" "ignore"
    }

    model {
        platformEng = person "Platform / Security Engineer" "Owns the hardening policy and the registry roster; operates houba as the single front door for external images."
        productTeam = person "Product / Application Team" "Declares its imports as MirrorPolicy files and consumes the hardened, stamped images."
        incidentResponder = person "Incident Responder (SRE / Security)" "At CVE time, computes the blast-radius from houba's provenance stamp."

        houba = softwareSystem "houba" "Single front door / stamper: mirrors external container images, optionally rebuilds them through a hardening policy, and stamps them with standardized, portable provenance." "Target" {
            # Documentation + decisions attached to houba (rendered in the viewer's panes):
            #   !docs → the design overview (docs/architecture/design.md).
            #   !adrs → the design specs as ADRs (docs/architecture/decisions/), linking out
            #           to the full specs under docs/superpowers/specs/.
            !docs design.md
            !adrs decisions

            houbaCli = container "houba CLI" "Reconcile engine: loads MirrorPolicy files, mirrors or rebuilds images and stamps them with provenance. Runs as a CLI / Job; the runtime image bundles regctl + buildctl." "Python · Typer" {

                group "CLI" {
                    cliMain = component "main" "Typer entrypoint; maps exceptions to exit codes." "Typer"
                    cliReconcile = component "reconcile" "The reconcile command: builds the composition root, runs the loop, renders the report." "Typer"
                    cliPurge = component "purge" "The purge command: scans pending-deletion marks, queries the usage oracle, applies hard-deletes for safely-unused tags." "Typer"
                    cliRender = component "render" "Formats the RunReport to stdout (text / JSON)." "Python"
                    cliDi = component "_di" "Composition root: wires ports to adapters." "Python"
                }
                group "Use cases" {
                    ucLoader = component "loader" "Loads and parses every MirrorPolicy file in a directory." "Python"
                    ucReconcile = component "reconcile_policies" "Orchestrator: concurrent plan-then-apply over all policies, isolated per policy, shardable for scale-out." "Python"
                    ucPurge = component "purge (use case)" "Catalog-walks the registry for pending-deletion referrers; asks the usage oracle per digest; hard-deletes only the safely-unused. Fail-closed: oracle error ⇒ nothing purged." "Python"
                    ucReport = component "report" "RunReport contract + worst-wins exit code." "Pydantic"
                }
                group "Domain (pure)" {
                    domSchema = component "policy schema" "MirrorPolicy model + published JSON Schema." "Pydantic" "Domain"
                    domPlanning = component "planning pipeline" "Tag selection, aliases, semver, variants, expand, reconcile plan, collision, sharding." "Pure Python" "Domain"
                    domTransform = component "transform engine" "Pluggable transform-step vocabulary: base, steps, registry, render, version." "Pure Python" "Domain"
                    domStamp = component "provenance stamp" "Builds the OCI-standard + io.houba.* provenance annotations." "Pure Python" "Domain"
                    domAttestation = component "attestation predicate" "Builds the in-toto transform Statement (predicate type /v1)." "Pure Python" "Domain"
                }
                group "Ports" {
                    portRegistry = component "RegistryPort" "OCI registry ops: list, inspect, copy, annotate, delete, login, referrer list/put/delete; list_repositories (catalog walk for purge)." "typing.Protocol" "Port"
                    portBuilder = component "ImageBuilderPort" "Build and push an image from a Dockerfile + context." "typing.Protocol" "Port"
                    portReporter = component "Reporter" "In-flight reconcile event journal." "typing.Protocol" "Port"
                    portClock = component "ClockPort" "Injectable now()." "typing.Protocol" "Port"
                    portUsageOracle = component "UsageOraclePort" "Was this image digest seen in prod since a given timestamp? (stateless, point-in-time query)." "typing.Protocol" "Port"
                    portAttestor = component "AttestorPort" "Sign an in-toto Statement (DSSE) + attach it as an OCI referrer." "typing.Protocol" "Port"
                }
                group "Adapters" {
                    adRegctl = component "RegctlAdapter" "Drives the regctl CLI via subprocess." "regctl" "Adapter"
                    adBuildkit = component "BuildkitAdapter" "Drives buildctl against buildkitd via subprocess." "buildctl" "Adapter"
                    adReporter = component "StructlogReporter" "Writes the event journal to stderr." "structlog" "Adapter"
                    adClock = component "SystemClock" "OS wall clock." "stdlib" "Adapter"
                    adUsageOracle = component "CommandUsageAdapter" "Shells out to HOUBA_USAGE_ORACLE_CMD; passes digest + idle window via stdin (JSON); expects {last_seen} on stdout." "subprocess" "Adapter"
                    adCosign = component "CosignAdapter" "Drives the cosign CLI via subprocess (keyless | kms | key)." "cosign" "Adapter"
                }
                config = component "config" "Reads HOUBA_* settings + roster resolvers — the only os.environ reader." "Pydantic Settings"

                # Coarse layer components — rendered only by the synthetic "Hexagon" view
                # (the detailed Component view excludes them). They sit alongside the
                # fine-grained components above, one abstraction level up.
                layCli = component "cli" "Thin Typer entrypoint + composition root (_di)." "driving side" "Layer"
                layUc = component "use cases" "Orchestrates the reconcile flow; depends only on ports." "application" "Layer"
                layDomain = component "domain" "Pure core: policy schema, planning, transforms, provenance — no I/O." "pure core" "Layer,Domain"
                layPorts = component "ports" "typing.Protocol interfaces — the hexagon's boundary." "boundary" "Layer,Port"
                layAdapters = component "adapters" "Implement the ports; reach the external systems (subprocess / stdlib)." "driven side" "Layer,Adapter"
            }
        }

        sourceRegistries = softwareSystem "Source Registries" "External public OCI registries (Docker Hub, Quay, GHCR) the images originate from." "External"
        destRegistries = softwareSystem "Destination Registries" "The organization's private OCI registries — any dist-spec registry (Harbor, Zot, …); destination for the stamped images, addressed generically via regctl." "External"
        buildkit = softwareSystem "BuildKit" "OCI build engine houba drives to rebuild and harden images." "External"
        packageMirror = softwareSystem "Internal Package Mirror" "The organization's internal apt/apk mirror; the hardening rebuild rewrites the image's package sources to it." "External"
        observability = softwareSystem "Observability / CMDB" "The organization's existing query stack; reads the provenance stamp to answer blast-radius questions during an incident." "External,Downstream"
        reaper = softwareSystem "Deletion reaper (external)" "Verifies prod usage and purges tags houba marked pending-deletion." "External,Downstream"
        usageOracle = softwareSystem "Usage oracle / observability" "Answers 'was this image's content seen in production lately?' (e.g. Datadog). Queried point-in-time by houba purge; never owned by houba." "External"
        signingService = softwareSystem "Signing / Key service" "KMS or Fulcio (keyless CA) that houba's attestor uses to sign in-toto attestations (DSSE). Trust is org configuration, not baked in." "External"
        transparencyLog = softwareSystem "Transparency log (Rekor)" "Optional append-only signature log; blank in air-gapped orgs. houba can point at one but never deploys it." "External,Downstream"

        platformEng -> houba "Configures the hardening policy + registry roster, runs / schedules reconcile" "CLI"
        productTeam -> houba "Declares its imports as MirrorPolicy files" "YAML"
        houba -> sourceRegistries "Lists tags, inspects digests, copies images" "regctl"
        houba -> destRegistries "Reads mirror state; copies, stamps, retags, deletes" "regctl (dist-spec)"
        houba -> buildkit "Submits the hardening rebuild (internal CA trust, package mirror)" "buildctl"
        buildkit -> packageMirror "Pulls packages during the hardening rebuild" "apt / apk"
        productTeam -> destRegistries "Pulls the hardened images" "docker pull (OCI)"
        observability -> destRegistries "Reads provenance stamps on images" "scan / API" "DataCoupling"
        incidentResponder -> observability "Queries blast-radius (at CVE time)" "Query UI"
        reaper -> destRegistries "Discovers pending-deletion referrers, verifies usage, purges" "OCI referrers API" "DataCoupling"
        houba -> usageOracle "Queries prod usage at purge time (houba purge)" "subprocess (HOUBA_USAGE_ORACLE_CMD)"
        houba -> signingService "Signs in-toto attestations (DSSE)" "cosign"
        houba -> transparencyLog "Records the signature (optional; blank => skipped)" "cosign / rekor"

        # Component-level relationships — the source of truth for the Component view.
        # Structurizr implies the container/system-level edges for the views above
        # (the explicit system-level edges already declared suppress duplicate implied ones).
        platformEng -> cliReconcile "Configures policy + roster, runs / schedules reconcile" "CLI"
        productTeam -> ucLoader "Provides MirrorPolicy files" "YAML"

        cliMain -> cliReconcile "Registers the command" "Typer"
        cliMain -> cliPurge "Registers the command" "Typer"
        cliPurge -> cliDi "Builds the composition root" "Python"
        cliPurge -> ucPurge "Runs the purge" "Python"
        cliPurge -> portClock "Reads now()" "Protocol"
        cliReconcile -> cliDi "Builds the composition root" "Python"
        cliReconcile -> ucLoader "Loads policies" "Python"
        cliReconcile -> ucReconcile "Runs reconciliation" "Python"
        cliReconcile -> cliRender "Renders the report" "Python"
        cliReconcile -> portClock "Reads now()" "Protocol"
        cliDi -> config "Reads HOUBA_* settings" "Pydantic Settings"
        cliDi -> adRegctl "Wires" "DI"
        cliDi -> adBuildkit "Wires" "DI"
        cliDi -> adReporter "Wires" "DI"
        cliDi -> adClock "Wires" "DI"
        cliDi -> adUsageOracle "Wires" "DI"

        ucLoader -> domSchema "Parses MirrorPolicy" "Pydantic"
        ucReconcile -> ucReport "Builds the RunReport" "Python"
        ucReconcile -> domPlanning "Computes the import / update / delete plan" "Python"
        ucReconcile -> domTransform "Renders & versions transforms" "Python"
        ucReconcile -> domStamp "Builds provenance annotations" "Python"
        ucReconcile -> portRegistry "Uses" "Protocol"
        ucReconcile -> portBuilder "Uses" "Protocol"
        ucReconcile -> portReporter "Uses" "Protocol"

        ucPurge -> portRegistry "Lists repos + referrers; hard-deletes purged tags" "Protocol"
        ucPurge -> portUsageOracle "Was this digest seen in prod?" "Protocol"
        ucPurge -> portClock "Computes idle window" "Protocol"

        adRegctl -> portRegistry "Implements" "Protocol"
        adBuildkit -> portBuilder "Implements" "Protocol"
        adReporter -> portReporter "Implements" "Protocol"
        adClock -> portClock "Implements" "Protocol"
        adUsageOracle -> portUsageOracle "Implements" "Protocol"

        adRegctl -> sourceRegistries "Lists tags, inspects digests, copies images" "regctl"
        adRegctl -> destRegistries "Reads mirror state; copies, stamps, retags, deletes" "regctl (dist-spec)"
        adBuildkit -> buildkit "Submits the hardening rebuild (internal CA trust, package mirror)" "buildctl"
        adUsageOracle -> usageOracle "Queries prod usage (HOUBA_USAGE_ORACLE_CMD)" "subprocess (stdin/stdout JSON)"

        ucReconcile -> domAttestation "Builds the transform Statement (rebuild path)" "Python"
        ucReconcile -> portAttestor "Signs the transform predicate (rebuild path)" "Protocol"
        cliDi -> adCosign "Wires" "DI"
        adCosign -> portAttestor "Implements" "Protocol"
        adCosign -> signingService "Signs attestations (DSSE)" "cosign"
        adCosign -> transparencyLog "Records the signature (optional)" "cosign / rekor"

        # Coarse hexagon relationships — rendered only in the synthetic "Hexagon" view.
        platformEng -> layCli "Runs / schedules reconcile" "CLI"
        productTeam -> layCli "Provides MirrorPolicy files" "YAML"
        layCli -> layUc "Invokes use cases" "Python"
        layCli -> config "Reads settings" "Pydantic Settings"
        layCli -> layAdapters "Wires (composition root)" "DI"
        layUc -> layDomain "Orchestrates pure logic" "Python"
        layUc -> layPorts "Depends on" "Protocol"
        layAdapters -> layPorts "Implement" "Protocol"
        layAdapters -> sourceRegistries "Lists, inspects, copies images" "regctl"
        layAdapters -> destRegistries "Copies, stamps, retags, deletes" "regctl"
        layAdapters -> buildkit "Submits the hardening rebuild" "buildctl"
        layAdapters -> usageOracle "Queries prod usage (purge)" "subprocess"
        layAdapters -> signingService "Signs attestations" "cosign"
        layAdapters -> transparencyLog "Records the signature (optional)" "cosign"

        # Deployments — one environment per worked example, each scoped to the kind overlay
        # that runs it (the demo IS the blueprint), plus the production blueprint. The old
        # single "Reference (kind)" view merged every overlay into one cramped diagram; these
        # split it by example so each reads cleanly and carries its own overlay facts.
        # See docs/superpowers/specs/2026-06-11-reference-deployment-design.md, deploy/overlays/,
        # and docs/examples/. Instance↔instance edges (houba→source/dest/buildkit,
        # buildkit→packageMirror) are auto-replicated from the model; only the infrastructure-node
        # edges are declared per environment.

        # ── busybox — copy path, overlay local-lite (the smallest end-to-end case).
        exBusybox = deploymentEnvironment "busybox · copy (local-lite)" {
            deploymentNode "Operator host" "Laptop / CI runner: runs kind, holds the policy clone" "macOS / Linux" {
                bbRepo = infrastructureNode "Policy repo" "docs/examples/busybox/busybox.yml — a merged PR is the front door" "git / GitOps"
                deploymentNode "kind cluster" "Single-node Kubernetes — overlay local-lite (copy path, no buildkit)" "kind" {
                    deploymentNode "namespace: houba" "houba workloads" "Namespace" {
                        deploymentNode "CronJob: houba-reconcile" "Suspended; one-shot via make demo-lite-run. Image houba:dev · team=platform · POLICY_DIR=docs/examples/busybox" "Kubernetes CronJob" {
                            bbHouba = containerInstance houbaCli
                            bbGit = infrastructureNode "git-sync sidecar" "Clones the policy repo into /policies" "git-sync"
                        }
                        bbBlast = infrastructureNode "Job: blast-radius" "BLAST_REPOS=demo/busybox — reads stamps, answers the CVE-time query" "regctl"
                    }
                    deploymentNode "namespace: registry" "Throwaway registry:2 — plain HTTP (tls_verify:false)" "Namespace" {
                        bbDest = softwareSystemInstance destRegistries
                    }
                }
            }
            deploymentNode "Internet" "Public registries, external to the cluster" "Network" {
                bbSrc = softwareSystemInstance sourceRegistries
            }
            bbGit -> bbRepo "Pulls policies" "git"
            bbBlast -> bbDest "Reads provenance stamps" "regctl" "DataCoupling"
        }

        # ── redis — same copy-path topology as busybox (shares local-lite); run in-cluster by
        #    repointing POLICY_DIR, or locally via `uv run houba reconcile docs/examples/redis`.
        exRedis = deploymentEnvironment "redis · copy (local-lite)" {
            deploymentNode "Operator host" "Laptop / CI runner: runs kind, holds the policy clone" "macOS / Linux" {
                rdRepo = infrastructureNode "Policy repo" "docs/examples/redis/redis.yml — semver 7.2.x, aliases track highest patch" "git / GitOps"
                deploymentNode "kind cluster" "Single-node Kubernetes — overlay local-lite (copy path, no buildkit)" "kind" {
                    deploymentNode "namespace: houba" "houba workloads" "Namespace" {
                        deploymentNode "CronJob: houba-reconcile" "Suspended; one-shot via make demo-lite-run. Image houba:dev · team=data-platform · POLICY_DIR=docs/examples/redis" "Kubernetes CronJob" {
                            rdHouba = containerInstance houbaCli
                            rdGit = infrastructureNode "git-sync sidecar" "Clones the policy repo into /policies" "git-sync"
                        }
                        rdBlast = infrastructureNode "Job: blast-radius" "BLAST_REPOS=demo/redis — reads stamps, answers the CVE-time query" "regctl"
                    }
                    deploymentNode "namespace: registry" "Throwaway registry:2 — plain HTTP (tls_verify:false)" "Namespace" {
                        rdDest = softwareSystemInstance destRegistries
                    }
                }
            }
            deploymentNode "Internet" "Public registries, external to the cluster" "Network" {
                rdSrc = softwareSystemInstance sourceRegistries
            }
            rdGit -> rdRepo "Pulls policies" "git"
            rdBlast -> rdDest "Reads provenance stamps" "regctl" "DataCoupling"
        }

        # ── pending-deletion — copy path with deletionMode:mark; an external reaper owns the purge.
        exPendingDeletion = deploymentEnvironment "pending-deletion · mark (local-lite + reaper)" {
            deploymentNode "Operator host" "Laptop / CI runner: runs kind, holds the policy clone" "macOS / Linux" {
                pdRepo = infrastructureNode "Policy repo" "docs/examples/pending-deletion/pending-deletion.yml — deletionMode: mark" "git / GitOps"
                deploymentNode "kind cluster" "Single-node Kubernetes — overlay local-lite (copy path, no buildkit)" "kind" {
                    deploymentNode "namespace: houba" "houba workloads" "Namespace" {
                        deploymentNode "CronJob: houba-reconcile" "On a dropped tag, attaches a pending-deletion OCI referrer instead of deleting. team=data-platform" "Kubernetes CronJob" {
                            pdHouba = containerInstance houbaCli
                            pdGit = infrastructureNode "git-sync sidecar" "Clones the policy repo into /policies" "git-sync"
                        }
                        pdBlast = infrastructureNode "Job: blast-radius" "BLAST_REPOS=demo/redis-delegated" "regctl"
                    }
                    deploymentNode "namespace: registry" "Throwaway registry:2 — marked tags stay pullable (digest unchanged)" "Namespace" {
                        pdDest = softwareSystemInstance destRegistries
                    }
                }
            }
            deploymentNode "Internet / org network" "External to the cluster" "Network" {
                pdSrc = softwareSystemInstance sourceRegistries
                pdReaper = softwareSystemInstance reaper
            }
            pdGit -> pdRepo "Pulls policies" "git"
            pdBlast -> pdDest "Reads provenance stamps" "regctl" "DataCoupling"
        }

        # ── timezone — rebuild path, runnable self-contained: buildkitd + registry:2, no Harbor,
        #    no org config. setTimezone fanned into -eu / -us variants. overlay local-transform.
        exTimezone = deploymentEnvironment "timezone · rebuild (local-transform)" {
            deploymentNode "Operator host" "Laptop / CI runner: runs kind, holds the policy clone" "macOS / Linux" {
                tzRepo = infrastructureNode "Policy repo" "docs/examples/timezone/debian.yml — fans bookworm-slim into -eu / -us variants" "git / GitOps"
                deploymentNode "kind cluster" "Single-node Kubernetes — overlay local-transform (rebuild path, self-contained: no Harbor, no org config)" "kind" {
                    deploymentNode "namespace: houba" "houba workloads" "Namespace" {
                        deploymentNode "CronJob: houba-reconcile" "Suspended; make demo-transform. team=platform · POLICY_DIR=docs/examples/timezone" "Kubernetes CronJob" {
                            tzHouba = containerInstance houbaCli
                            tzGit = infrastructureNode "git-sync sidecar" "Clones the policy repo into /policies" "git-sync"
                        }
                        deploymentNode "Deployment: buildkitd" "Rootless build engine; --config marks registry:2 as plain-HTTP for the push" "Kubernetes Deployment" {
                            tzBuild = softwareSystemInstance buildkit
                        }
                        tzBlast = infrastructureNode "Job: blast-radius" "BLAST_REPOS=demo/debian" "regctl"
                    }
                    deploymentNode "namespace: registry" "Throwaway registry:2 — plain HTTP; buildkit pushes the rebuilt images here" "Namespace" {
                        tzDest = softwareSystemInstance destRegistries
                    }
                }
            }
            deploymentNode "Internet" "Public registries, external to the cluster" "Network" {
                tzSrc = softwareSystemInstance sourceRegistries
            }
            tzGit -> tzRepo "Pulls policies" "git"
            tzBlast -> tzDest "Reads provenance stamps" "regctl" "DataCoupling"
        }

        # ── hardened — rebuild path into Harbor with org config (injectCA + rewritePackageSources).
        #    overlay local-full: buildkitd, CA bundle mounted, ExternalSecret for Harbor push, mirror.
        exHardened = deploymentEnvironment "hardened · rebuild + Harbor (local-full)" {
            deploymentNode "Operator host" "Laptop / CI runner: runs kind, holds the policy clone" "macOS / Linux" {
                hdRepo = infrastructureNode "Policy repo" "docs/examples/hardened/redis.yml — injectCA + rewritePackageSources (names only; data in config)" "git / GitOps"
                deploymentNode "kind cluster" "Single-node Kubernetes — overlay local-full (rebuild + Harbor + org config)" "kind" {
                    deploymentNode "namespace: houba" "houba workloads" "Namespace" {
                        deploymentNode "CronJob: houba-reconcile" "Suspended; make demo-full-run. HOUBA_TRANSFORM_CA_CERTS + _PACKAGE_MIRRORS set · team=data-platform" "Kubernetes CronJob" {
                            hdHouba = containerInstance houbaCli
                            hdGit = infrastructureNode "git-sync sidecar" "Clones the policy repo into /policies" "git-sync"
                            hdCA = infrastructureNode "CA bundle (corp-root.pem)" "ConfigMap mounted at /etc/houba/certs into the container trust path" "ConfigMap"
                        }
                        deploymentNode "Deployment: buildkitd" "Rootless build engine; runs injectCA + rewritePackageSources" "Kubernetes Deployment" {
                            hdBuild = softwareSystemInstance buildkit
                        }
                        hdSecret = infrastructureNode "ExternalSecret → robot$houba" "Harbor push token (secret-registries.yaml)" "ExternalSecret"
                        hdBlast = infrastructureNode "Job: blast-radius" "BLAST_REPOS=hardened/redis" "regctl"
                    }
                    deploymentNode "Harbor (Helm release)" "Installed separately via Helm — TLS; project: hardened" "Harbor" {
                        hdDest = softwareSystemInstance destRegistries
                    }
                }
            }
            deploymentNode "Internet / org network" "External to the cluster" "Network" {
                hdSrc = softwareSystemInstance sourceRegistries
                hdPkg = softwareSystemInstance packageMirror
            }
            hdGit -> hdRepo "Pulls policies" "git"
            hdHouba -> hdCA "Mounts the CA bundle as the injectCA trust input" "volume"
            hdBlast -> hdDest "Reads provenance stamps" "regctl / API" "DataCoupling"
            hdSecret -> hdDest "Supplies push credentials" "token"
        }

        # ── Production blueprint — the prod overlay: real cluster, ExternalSecret-sourced creds,
        #    org policy repo, pinned published image, hourly schedule, rebuild add-on present.
        #    Same base manifests as the demos above (anti-drift): the demo IS the blueprint.
        prod = deploymentEnvironment "Production blueprint (prod overlay)" {
            deploymentNode "Org GitOps host" "e.g. gitlab.example.com/platform/houba-policies" "Git server" {
                prRepo = infrastructureNode "Policy repo (org)" "The front door: a merged PR. POLICY_DIR=/policies/current — reconciles the whole tree" "git"
            }
            deploymentNode "Production Kubernetes cluster" "Real cluster (not kind) — same kustomize base as the demos (anti-drift)" "Kubernetes" {
                deploymentNode "namespace: houba" "houba workloads" "Namespace" {
                    deploymentNode "CronJob: houba-reconcile" "Hourly (not suspended). Image ghcr.io/trivoallan/houba:v0.2.0" "Kubernetes CronJob" {
                        prHouba = containerInstance houbaCli
                        prGit = infrastructureNode "git-sync sidecar" "Clones the org policy repo into /policies" "git-sync"
                    }
                    deploymentNode "Deployment: buildkitd" "Rebuild add-on (rootless build engine)" "Kubernetes Deployment" {
                        prBuild = softwareSystemInstance buildkit
                    }
                    prSecret = infrastructureNode "ExternalSecret" "Pulls registry credentials from the org secret store" "ExternalSecret"
                    prBlast = infrastructureNode "Job: blast-radius" "Walks the mirrored namespaces; stand-in for the org observability / CMDB stack" "regctl"
                }
            }
            deploymentNode "Org private registry" "Any dist-spec registry (Harbor / Zot …) — TLS" "OCI registry" {
                prDest = softwareSystemInstance destRegistries
            }
            deploymentNode "Internet / org network" "External to the cluster" "Network" {
                prSrc = softwareSystemInstance sourceRegistries
                prPkg = softwareSystemInstance packageMirror
            }
            prGit -> prRepo "Pulls policies" "git"
            prBlast -> prDest "Reads provenance stamps" "regctl / API" "DataCoupling"
            prSecret -> prDest "Supplies registry credentials" "token"
        }
    }

    views {
        systemLandscape "Landscape" "houba in its enterprise context, through to incident-time blast-radius." {
            include *
            autolayout lr
        }

        systemContext houba "Context" "houba and the systems it integrates with directly." {
            include *
            autolayout lr
        }

        container houba "Container" "houba as a single deployable CLI container, and the external systems it drives." {
            include *
            autolayout lr
        }

        component houbaCli "Hexagon" "Synthetic hexagonal overview: cli → use cases → domain, with ports ← adapters making the dependency inversion explicit (use cases and adapters both point at the ports). The driven adapters reach the external systems." {
            include layCli layUc layDomain layPorts layAdapters config platformEng productTeam sourceRegistries destRegistries buildkit usageOracle signingService transparencyLog
            autolayout lr
        }

        component houbaCli "Component" "Inside the houba CLI: every fine-grained component of the hexagonal layers — cli, use cases, the pure domain (4 concerns), the ports, and the adapters that reach the external systems." {
            include *
            exclude layCli layUc layDomain layPorts layAdapters
            autolayout lr
        }

        # One deployment view per worked example (each = its kind overlay), plus the prod
        # blueprint. The same kustomize base underlies them all — the demo IS the blueprint.
        deployment houba "busybox · copy (local-lite)" "DeployBusybox" "Copy path, smallest case: houba mirrors + stamps busybox into a throwaway registry:2 (HTTP), no buildkit. Overlay local-lite." {
            include *
            autolayout lr
        }
        deployment houba "redis · copy (local-lite)" "DeployRedis" "Copy path over a real image (redis 7.2.x): same local-lite topology as busybox, semver aliases. Run in-cluster or locally." {
            include *
            autolayout lr
        }
        deployment houba "pending-deletion · mark (local-lite + reaper)" "DeployPendingDeletion" "Copy path with deletionMode:mark — dropped tags get a pending-deletion OCI referrer; an external reaper owns the purge." {
            include *
            autolayout lr
        }
        deployment houba "timezone · rebuild (local-transform)" "DeployTimezone" "Rebuild path, self-contained: buildkitd rebuilds debian through setTimezone into -eu/-us variants, pushes to registry:2 (HTTP). No Harbor, no org config. Overlay local-transform." {
            include *
            autolayout lr
        }
        deployment houba "hardened · rebuild + Harbor (local-full)" "DeployHardened" "Rebuild path with org config: buildkitd injects CA + rewrites package sources, pushes the hardened redis to Harbor (TLS) via an ExternalSecret-sourced robot token. Overlay local-full." {
            include *
            autolayout lr
        }
        deployment houba "Production blueprint (prod overlay)" "DeployProd" "The production blueprint: a real cluster running the same kustomize base, with ExternalSecret-sourced creds, the org policy repo, a pinned published image, hourly schedule, and the rebuild add-on." {
            include *
            autolayout lr
        }

        styles {
            element "Element" {
                shape RoundedBox
                color #ffffff
            }
            element "Person" {
                shape Person
                background #52606d
            }
            element "Software System" {
                background #69707a
            }
            element "External" {
                background #69707a
            }
            element "Target" {
                background #1f6feb
            }
            element "Downstream" {
                background #0f766e
            }
            element "Infrastructure Node" {
                shape RoundedBox
                background #8a94a0
            }
            element "Container" {
                background #2563c9
                color #ffffff
            }
            element "Component" {
                shape RoundedBox
                background #cdd5df
                color #1f2933
            }
            element "Domain" {
                background #b6e3d4
                color #04342c
            }
            element "Port" {
                background #e9d8fd
                color #322659
            }
            element "Adapter" {
                background #fed7aa
                color #4a1b0c
            }
            element "Layer" {
                strokeWidth 6
            }
            relationship "Relationship" {
                routing Orthogonal
            }
            relationship "DataCoupling" {
                dashed true
            }
        }
    }

    configuration {
        scope softwaresystem
    }
}
