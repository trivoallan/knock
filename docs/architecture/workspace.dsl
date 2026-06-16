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
                    cliAudit = component "audit" "The audit command: catalog-walks the registry, reports images missing the provenance stamp." "Typer"
                    cliAttach = component "attach" "The attach command: ingests an upstream scan report and attaches it as a stamped OCI referrer." "Typer"
                    cliGc = component "gc" "The gc command: catalog-walks the registry and deletes superseded scan-result referrers, keeping the N newest per (tool, format) older than a grace window." "Typer"
                    cliRender = component "render" "Formats the RunReport to stdout (text / JSON)." "Python"
                    cliDi = component "_di" "Composition root: wires ports to adapters." "Python"
                }
                group "Use cases" {
                    ucLoader = component "loader" "Loads and parses every MirrorPolicy file in a directory." "Python"
                    ucReconcile = component "reconcile_policies" "Orchestrator: concurrent plan-then-apply over all policies, isolated per policy, shardable for scale-out." "Python"
                    ucPurge = component "purge (use case)" "Catalog-walks the registry for pending-deletion referrers; asks the usage oracle per digest; hard-deletes only the safely-unused. Fail-closed: oracle error ⇒ nothing purged." "Python"
                    ucAudit = component "audit (use case)" "Catalog-walks the registry and classifies each image as stamped or not; emits the coverage report + exit code." "Python"
                    ucAttach = component "attach (use case)" "Resolves the subject digest, summarizes the ingested scan report, and puts it as a stamped OCI referrer." "Python"
                    ucGc = component "gc (use case)" "Catalog-walks the registry for scan-result referrers and collects the superseded ones (keep N newest per (tool, format) older than a grace window); pure temporal decision, no usage oracle. Dry-run by default." "Python"
                    ucReport = component "report" "RunReport contract + worst-wins exit code." "Pydantic"
                    ucRegistrySession = component "registry_session" "Shared use-case helper: configure TLS/CA + login once per host (idempotent via caller-owned logged_in set). Used by reconcile, audit, and attach." "Python"
                }
                group "Domain (pure)" {
                    domSchema = component "policy schema" "MirrorPolicy model + published JSON Schema." "Pydantic" "Domain"
                    domPlanning = component "planning pipeline" "Tag selection, aliases, semver, variants, expand, reconcile plan, collision, sharding, retention." "Pure Python" "Domain"
                    domTransform = component "transform engine" "Pluggable transform-step vocabulary: base, steps, registry, render, version." "Pure Python" "Domain"
                    domStamp = component "provenance stamp" "Builds the OCI-standard + io.houba.* provenance annotations." "Pure Python" "Domain"
                    domCoverage = component "coverage" "Pure stamp-presence predicate: is the image houba-stamped?" "Pure Python" "Domain"
                    domAttestation = component "attestation predicate" "Builds the in-toto transform Statement (predicate type /v1)." "Pure Python" "Domain"
                    domScan = component "scan ingestion" "Detects the scan-report format, parses it (e.g. SARIF), and summarizes it into stamp annotations." "Pure Python" "Domain"
                    domSbom = component "SBOM facts" "SBOM format media-types and referrer annotation builder (domain/sbom.py)." "Pure Python" "Domain"
                }
                group "Ports" {
                    portRegistry = component "RegistryPort" "OCI registry ops: list, inspect, copy, annotate, delete, login, referrer list/put/delete; list_repositories (catalog walk for purge)." "typing.Protocol" "Port"
                    portBuilder = component "ImageBuilderPort" "Build and push an image from a Dockerfile + context." "typing.Protocol" "Port"
                    portReporter = component "Reporter" "In-flight reconcile event journal." "typing.Protocol" "Port"
                    portClock = component "ClockPort" "Injectable now()." "typing.Protocol" "Port"
                    portUsageOracle = component "UsageOraclePort" "Was this image digest seen in prod since a given timestamp? (stateless, point-in-time query)." "typing.Protocol" "Port"
                    portAttestor = component "AttestorPort" "Sign an in-toto Statement (DSSE) + attach it as an OCI referrer." "typing.Protocol" "Port"
                    portSbomGenerator = component "SbomGeneratorPort" "Generate package-level SBOM(s) for a placed image by digest; returns one document per format." "typing.Protocol" "Port"
                }
                group "Adapters" {
                    adRegctl = component "RegctlAdapter" "Drives the regctl CLI via subprocess." "regctl" "Adapter"
                    adBuildkit = component "BuildkitAdapter" "Drives buildctl against buildkitd via subprocess (provenance attestation; no SBOM — superseded by SyftAdapter)." "buildctl" "Adapter"
                    adReporter = component "StructlogReporter" "Writes the event journal to stderr." "structlog" "Adapter"
                    adClock = component "SystemClock" "OS wall clock." "stdlib" "Adapter"
                    adUsageOracle = component "CommandUsageAdapter" "Shells out to HOUBA_USAGE_ORACLE_CMD; passes digest + idle window via stdin (JSON); expects {last_seen} on stdout." "subprocess" "Adapter"
                    adCosign = component "CosignAdapter" "Drives the cosign CLI via subprocess (keyless | kms | key)." "cosign" "Adapter"
                    adSyft = component "SyftAdapter" "Drives the syft CLI via subprocess; config-file auth/TLS; lazy binary resolution." "syft" "Adapter"
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
        upstreamScanner = softwareSystem "Upstream Scanner" "Produces vulnerability / EOL scan reports (CI pipeline, registry-native scanner, or scan service). houba ingests the report; it never calls the scanner." "External"
        argocd = softwareSystem "ArgoCD" "GitOps controller: the App-of-Apps that syncs the houba install from git. This IS the reference deployment — and the demo on kind. The kubectl apply -k overlays/local path is the inner-loop escape hatch, not a separate blueprint." "External"

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
        upstreamScanner -> houba "Produces scan reports ingested by" "SARIF / file"
        argocd -> houba "Syncs the install manifests from git into the cluster (App-of-Apps reference)" "GitOps"

        # Component-level relationships — the source of truth for the Component view.
        # Structurizr implies the container/system-level edges for the views above
        # (the explicit system-level edges already declared suppress duplicate implied ones).
        platformEng -> cliReconcile "Configures policy + roster, runs / schedules reconcile" "CLI"
        productTeam -> ucLoader "Provides MirrorPolicy files" "YAML"

        cliMain -> cliReconcile "Registers the command" "Typer"
        cliMain -> cliPurge "Registers the command" "Typer"
        cliMain -> cliAudit "Registers the command" "Typer"
        cliMain -> cliAttach "Registers the command" "Typer"
        cliMain -> cliGc "Registers the command" "Typer"
        cliAudit -> cliDi "Builds the composition root" "Python"
        cliAudit -> ucAudit "Runs the audit" "Python"
        ucAudit -> domCoverage "Classifies each image" "Python"
        ucAudit -> portRegistry "Catalog-walks + reads annotations" "Protocol"
        ucAudit -> ucRegistrySession "Configures TLS/CA + login per registry" "Python"
        cliAttach -> cliDi "Builds the composition root" "Python"
        cliAttach -> ucAttach "Runs the ingest" "Python"
        upstreamScanner -> ucAttach "Provides scan reports" "SARIF / file"
        ucAttach -> domScan "Detects format, parses & summarizes the report" "Python"
        ucAttach -> portRegistry "Resolves the subject digest + puts the scan referrer" "Protocol"
        ucAttach -> portClock "Reads now()" "Protocol"
        ucAttach -> ucRegistrySession "Configures TLS/CA + login per registry (host-match or --registry override)" "Python"
        cliPurge -> cliDi "Builds the composition root" "Python"
        cliPurge -> ucPurge "Runs the purge" "Python"
        cliPurge -> portClock "Reads now()" "Protocol"
        cliGc -> cliDi "Builds the composition root" "Python"
        cliGc -> ucGc "Runs the gc" "Python"
        cliGc -> portClock "Reads now()" "Protocol"
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
        ucReconcile -> ucRegistrySession "Configures TLS/CA + login per registry" "Python"

        ucPurge -> portRegistry "Lists repos + referrers; hard-deletes purged tags" "Protocol"
        ucPurge -> portUsageOracle "Was this digest seen in prod?" "Protocol"
        ucPurge -> portClock "Computes idle window" "Protocol"

        ucGc -> portRegistry "Lists repos + scan referrers; deletes superseded ones" "Protocol"
        ucGc -> ucRegistrySession "Configures TLS/CA + login per registry" "Python"

        ucRegistrySession -> portRegistry "Calls configure_registry + login" "Protocol"

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
        ucReconcile -> domSbom "Builds SBOM referrer annotations (both paths)" "Python"
        cliDi -> adCosign "Wires" "DI"
        adCosign -> portAttestor "Implements" "Protocol"
        adCosign -> signingService "Signs attestations (DSSE)" "cosign"
        adCosign -> transparencyLog "Records the signature (optional)" "cosign / rekor"

        cliDi -> adSyft "Wires" "DI"
        adSyft -> portSbomGenerator "Implements" "Protocol"
        ucReconcile -> portSbomGenerator "Generates SBOM(s) after placing each image (both paths)" "Protocol"
        adSyft -> destRegistries "Scans the placed image by digest" "syft"

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

        # ── The reference deployment — the Argo App-of-Apps that IS the demo. On kind it is
        #    the demo (`make demo`); the same App-of-Apps adopts to a real cluster (swap repo,
        #    vault, registry, image). Thesis-minimum operators: ESO + OpenBao (wave 0), houba +
        #    buildkitd (wave 1). KEDA + Prometheus autoscaling is an optional add-on
        #    (components/keda-buildkitd), deliberately NOT on this path.
        refEnv = deploymentEnvironment "Reference — Argo App-of-Apps (the demo)" {
            deploymentNode "Git host" "github.com/trivoallan/houba (or a fork) — deploy/argocd/" "Git server" {
                rfRepo = infrastructureNode "Manifests repo" "root.yaml + apps/ + sources/* — a merged PR is the front door" "git / GitOps"
                rfPolicyRepo = infrastructureNode "Policy repo (org)" "POLICY_REPO_URL — git-sync clones it; POLICY_DIR=docs/examples/reference (busybox copy + debian rebuild). ArgoCD never touches policies." "git / GitOps"
            }
            deploymentNode "Kubernetes cluster" "kind (the demo) or a real cluster — same manifests (anti-drift)" "Kubernetes" {
                deploymentNode "namespace: argocd" "ArgoCD controller" "Namespace" {
                    rfRoot = infrastructureNode "Application: houba-root" "App-of-Apps; syncs the apps/ children from git (no demo/prod split)" "ArgoCD"
                    rfArgo = softwareSystemInstance argocd
                }
                deploymentNode "namespace: houba" "houba workloads (wave 1)" "Namespace" {
                    deploymentNode "CronJob: houba-reconcile" "BUILDKIT_HOST wired via config (no CronJob patch). On kind: image houba:dev; reconciles the reference policy (copy + rebuild)" "Kubernetes CronJob" {
                        rfHouba = containerInstance houbaCli
                        rfGit = infrastructureNode "git-sync sidecar" "Clones the policy repo into /policies" "git-sync"
                    }
                    deploymentNode "Deployment: buildkitd (own app)" "Rebuild add-on (rootless build engine) — its own ArgoCD Application" "Kubernetes Deployment" {
                        rfBuild = softwareSystemInstance buildkit
                    }
                    rfEsObj = infrastructureNode "ExternalSecret + ClusterSecretStore" "houba-secret-store → OpenBao (ESO vault provider)" "ExternalSecret"
                    rfBlast = infrastructureNode "Job: blast-radius" "BLAST_REPOS=demo/busybox demo/debian — reads stamps, answers the CVE-time query" "regctl"
                    rfGc = infrastructureNode "CronJob: houba-gc" "Weekly houba gc --apply — collects superseded scan referrers (keep=2/older-than=30d). No git-sync/policies; walks the roster only." "Kubernetes CronJob"
                    rfDt = infrastructureNode "Deployment: dependency-track (own app)" "Worked-example SBOM consumer (apiserver + frontend, embedded H2) — its own ArgoCD Application (ADR 0033). Currency layer: package-level blast-radius. DT is CycloneDX-only; houba's SPDX is converted by the publish glue." "Kubernetes Deployment"
                    rfPublishSbom = infrastructureNode "Job: houba-publish-sbom" "Glue image (houba + syft): pulls each rebuilt image's SPDX SBOM attestation, converts to CycloneDX, uploads to DT. Twin of the blast-radius consumer." "Kubernetes Job"
                }
                deploymentNode "namespace: external-secrets" "ESO operator (wave 0)" "Namespace" {
                    rfEso = infrastructureNode "External Secrets Operator" "Helm child; materializes the registry roster Secret" "ESO"
                }
                deploymentNode "namespace: openbao" "Secret backend (wave 0)" "Namespace" {
                    rfBao = infrastructureNode "OpenBao" "Helm child (dev mode on kind); holds houba/registries" "OpenBao"
                }
                deploymentNode "namespace: registry" "Throwaway Zot — OCI registry + built-in web UI (make registry-ui); applied out-of-band by make demo, ArgoCD does not manage it" "Namespace" {
                    rfDest = softwareSystemInstance destRegistries
                }
            }
            deploymentNode "Internet / org network" "External to the cluster" "Network" {
                rfSrc = softwareSystemInstance sourceRegistries
            }
            rfArgo -> rfRepo "Pulls manifests (App-of-Apps)" "git" "DataCoupling"
            rfRoot -> rfHouba "Syncs the houba install" "ArgoCD"
            rfRoot -> rfBuild "Syncs the buildkitd app" "ArgoCD"
            rfEso -> rfBao "Reads houba/registries" "vault API" "DataCoupling"
            rfEsObj -> rfEso "Requests the roster Secret" "ESO"
            rfGit -> rfPolicyRepo "Pulls policies" "git"
            rfBlast -> rfDest "Reads provenance stamps" "regctl" "DataCoupling"
            rfGc -> rfDest "Collects superseded scan referrers" "regctl" "DataCoupling"
        }

        # ── The local inner-loop overlay — the escape hatch (`make local`, kubectl apply -k).
        #    Self-contained: buildkitd + a throwaway registry:2, a plain-secret roster, NO
        #    operators. Reconciles the SAME reference policy (busybox copy + debian rebuild) and
        #    renders local, uncommitted manifests (the App-of-Apps reads children from git).
        localEnv = deploymentEnvironment "Local — inner-loop overlay (make local)" {
            deploymentNode "Operator host" "Laptop / CI runner: runs kind, holds the policy clone" "macOS / Linux" {
                loRepo = infrastructureNode "Policy repo" "docs/examples/reference — busybox copy + debian rebuild (git-sync'd)" "git / GitOps"
                deploymentNode "kind cluster" "Single-node Kubernetes — overlay local (self-contained: buildkitd, no operators)" "kind" {
                    deploymentNode "namespace: houba" "houba workloads" "Namespace" {
                        deploymentNode "CronJob: houba-reconcile" "Suspended; one-shot via make local. Image houba:dev · team=platform · POLICY_DIR=docs/examples/reference" "Kubernetes CronJob" {
                            loHouba = containerInstance houbaCli
                            loGit = infrastructureNode "git-sync sidecar" "Clones the policy repo into /policies" "git-sync"
                        }
                        deploymentNode "Deployment: buildkitd" "Rootless build engine; pushes to the plain-HTTP Zot via registry.insecure derived from the roster tls_verify (generic component, no daemon config)" "Kubernetes Deployment" {
                            loBuild = softwareSystemInstance buildkit
                        }
                        loSecret = infrastructureNode "Secret: houba-registries" "Plain secret roster (no operators) — the inner-loop escape hatch" "Secret"
                        loBlast = infrastructureNode "Job: blast-radius" "BLAST_REPOS=demo/busybox demo/debian" "regctl"
                        loGc = infrastructureNode "CronJob: houba-gc" "Suspended (like reconcile); fired on demand. houba gc --apply over the roster." "Kubernetes CronJob"
                        loDt = infrastructureNode "Deployment: dependency-track (own app)" "Worked-example SBOM consumer (apiserver + frontend, embedded H2) — (ADR 0033). Currency layer: package-level blast-radius. DT is CycloneDX-only; houba's SPDX is converted by the publish glue." "Kubernetes Deployment"
                        loPublishSbom = infrastructureNode "Job: houba-publish-sbom" "Glue image (houba + syft): pulls each rebuilt image's SPDX SBOM attestation, converts to CycloneDX, uploads to DT. Twin of the blast-radius consumer." "Kubernetes Job"
                    }
                    deploymentNode "namespace: registry" "Throwaway Zot — plain HTTP; copied + rebuilt images pushed here; built-in web UI (make registry-ui)" "Namespace" {
                        loDest = softwareSystemInstance destRegistries
                    }
                }
            }
            deploymentNode "Internet" "Public registries, external to the cluster" "Network" {
                loSrc = softwareSystemInstance sourceRegistries
            }
            loGit -> loRepo "Pulls policies" "git"
            loBlast -> loDest "Reads provenance stamps" "regctl" "DataCoupling"
            loGc -> loDest "Collects superseded scan referrers" "regctl" "DataCoupling"
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

        # Two deployment views: the Argo reference (which is the demo) and the local
        # inner-loop overlay. The same kustomize base underlies both — the demo IS the blueprint.
        deployment houba "Reference — Argo App-of-Apps (the demo)" "DeployReference" "The single reference: an Argo App-of-Apps that is both the production blueprint and the kind demo. ESO + OpenBao (wave 0), houba + buildkitd (wave 1); the reference policy (busybox copy + debian rebuild); a throwaway Zot (registry + built-in UI) applied out-of-band. KEDA/Prometheus autoscaling is an optional add-on, not on this path." {
            include *
            autolayout lr
        }
        deployment houba "Local — inner-loop overlay (make local)" "DeployLocal" "The inner-loop escape hatch: kubectl apply -k overlays/local — buildkitd + a throwaway Zot (registry + built-in UI), a plain-secret roster, no operators. Reconciles the same reference policy (copy + rebuild) and renders local, uncommitted manifests." {
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
