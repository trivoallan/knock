workspace "houba" "Single front door / stamper for external container images." {

    model {
        platformEng = person "Platform / Security Engineer" "Owns the hardening policy and the registry roster; operates houba as the single front door for external images."
        productTeam = person "Product / Application Team" "Declares its imports as MirrorPolicy files and consumes the hardened, stamped images."
        incidentResponder = person "Incident Responder (SRE / Security)" "At CVE time, computes the blast-radius from houba's provenance stamp."

        houba = softwareSystem "houba" "Single front door / stamper: mirrors external container images, optionally rebuilds them through a hardening policy, and stamps them with standardized, portable provenance." "Target" {
            houbaCli = container "houba CLI" "Reconcile engine: loads MirrorPolicy files, mirrors or rebuilds images and stamps them with provenance. Runs as a CLI / Job; the runtime image bundles regctl + buildctl." "Python · Typer" {

                group "CLI" {
                    cliMain = component "main" "Typer entrypoint; maps exceptions to exit codes." "Typer"
                    cliReconcile = component "reconcile" "The reconcile command: builds the composition root, runs the loop, renders the report." "Typer"
                    cliRender = component "render" "Formats the RunReport to stdout (text / JSON)." "Python"
                    cliDi = component "_di" "Composition root: wires ports to adapters." "Python"
                }
                group "Use cases" {
                    ucLoader = component "loader" "Loads and parses every MirrorPolicy file in a directory." "Python"
                    ucReconcile = component "reconcile_policies" "Orchestrator: concurrent plan-then-apply over all policies, isolated per policy, shardable for scale-out." "Python"
                    ucReport = component "report" "RunReport contract + worst-wins exit code." "Pydantic"
                }
                group "Domain (pure)" {
                    domSchema = component "policy schema" "MirrorPolicy model + published JSON Schema." "Pydantic" "Domain"
                    domPlanning = component "planning pipeline" "Tag selection, aliases, semver, variants, expand, reconcile plan, collision, sharding." "Pure Python" "Domain"
                    domTransform = component "transform engine" "Pluggable transform-step vocabulary: base, steps, registry, render, version." "Pure Python" "Domain"
                    domStamp = component "provenance stamp" "Builds the OCI-standard + io.houba.* provenance annotations." "Pure Python" "Domain"
                }
                group "Ports" {
                    portRegistry = component "RegistryPort" "OCI registry ops: list, inspect, copy, annotate, delete, login." "typing.Protocol" "Port"
                    portBuilder = component "ImageBuilderPort" "Build and push an image from a Dockerfile + context." "typing.Protocol" "Port"
                    portReporter = component "Reporter" "In-flight reconcile event journal." "typing.Protocol" "Port"
                    portClock = component "ClockPort" "Injectable now()." "typing.Protocol" "Port"
                }
                group "Adapters" {
                    adRegctl = component "RegctlAdapter" "Drives the regctl CLI via subprocess." "regctl" "Adapter"
                    adBuildkit = component "BuildkitAdapter" "Drives buildctl against buildkitd via subprocess." "buildctl" "Adapter"
                    adReporter = component "StructlogReporter" "Writes the event journal to stderr." "structlog" "Adapter"
                    adClock = component "SystemClock" "OS wall clock." "stdlib" "Adapter"
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

        platformEng -> houba "Configures the hardening policy + registry roster, runs / schedules reconcile" "CLI"
        productTeam -> houba "Declares its imports as MirrorPolicy files" "YAML"
        houba -> sourceRegistries "Lists tags, inspects digests, copies images" "regctl"
        houba -> destRegistries "Reads mirror state; copies, stamps, retags, deletes" "regctl (dist-spec)"
        houba -> buildkit "Submits the hardening rebuild (internal CA trust, package mirror)" "buildctl"
        buildkit -> packageMirror "Pulls packages during the hardening rebuild" "apt / apk"
        productTeam -> destRegistries "Pulls the hardened images" "docker pull (OCI)"
        observability -> destRegistries "Reads provenance stamps on images" "scan / API" "DataCoupling"
        incidentResponder -> observability "Queries blast-radius (at CVE time)" "Query UI"

        # Component-level relationships — the source of truth for the Component view.
        # Structurizr implies the container/system-level edges for the views above
        # (the explicit system-level edges already declared suppress duplicate implied ones).
        platformEng -> cliReconcile "Configures policy + roster, runs / schedules reconcile" "CLI"
        productTeam -> ucLoader "Provides MirrorPolicy files" "YAML"

        cliMain -> cliReconcile "Registers the command"
        cliReconcile -> cliDi "Builds the composition root"
        cliReconcile -> ucLoader "Loads policies"
        cliReconcile -> ucReconcile "Runs reconciliation"
        cliReconcile -> cliRender "Renders the report"
        cliReconcile -> portClock "Reads now()"
        cliDi -> config "Reads HOUBA_* settings"
        cliDi -> adRegctl "Wires"
        cliDi -> adBuildkit "Wires"
        cliDi -> adReporter "Wires"
        cliDi -> adClock "Wires"

        ucLoader -> domSchema "Parses MirrorPolicy"
        ucReconcile -> ucReport "Builds the RunReport"
        ucReconcile -> domPlanning "Computes the import / update / delete plan"
        ucReconcile -> domTransform "Renders & versions transforms"
        ucReconcile -> domStamp "Builds provenance annotations"
        ucReconcile -> portRegistry "Uses"
        ucReconcile -> portBuilder "Uses"
        ucReconcile -> portReporter "Uses"

        adRegctl -> portRegistry "Implements"
        adBuildkit -> portBuilder "Implements"
        adReporter -> portReporter "Implements"
        adClock -> portClock "Implements"

        adRegctl -> sourceRegistries "Lists tags, inspects digests, copies images" "regctl"
        adRegctl -> destRegistries "Reads mirror state; copies, stamps, retags, deletes" "regctl (dist-spec)"
        adBuildkit -> buildkit "Submits the hardening rebuild (internal CA trust, package mirror)" "buildctl"

        # Coarse hexagon relationships — rendered only in the synthetic "Hexagon" view.
        platformEng -> layCli "Runs / schedules reconcile" "CLI"
        productTeam -> layCli "Provides MirrorPolicy files" "YAML"
        layCli -> layUc "Invokes use cases"
        layCli -> config "Reads settings"
        layCli -> layAdapters "Wires (composition root)"
        layUc -> layDomain "Orchestrates pure logic"
        layUc -> layPorts "Depends on"
        layAdapters -> layPorts "Implement"
        layAdapters -> sourceRegistries "Lists, inspects, copies images" "regctl"
        layAdapters -> destRegistries "Copies, stamps, retags, deletes" "regctl"
        layAdapters -> buildkit "Submits the hardening rebuild" "buildctl"

        # Reference deployment — kind-based, doubles as the production blueprint.
        # See docs/superpowers/specs/2026-06-11-reference-deployment-design.md.
        reference = deploymentEnvironment "Reference (kind)" {
            deploymentNode "Operator host (laptop / CI runner)" "Runs kind; hosts the policy repo clone" {
                policyRepo = infrastructureNode "Policy GitOps repo" "MirrorPolicy YAML; a merged PR is the front door" "git"

                deploymentNode "kind cluster" "Kubernetes, single node" "kind" {
                    deploymentNode "namespace: houba" "" "Kubernetes Namespace" {
                        deploymentNode "CronJob: houba-reconcile" "Hourly in prod; one-shot Job in demo" "Kubernetes CronJob" {
                            houbaInstance = softwareSystemInstance houba
                            gitSync = infrastructureNode "git-sync sidecar" "Syncs the policy repo into /policies" "git-sync"
                        }
                        deploymentNode "Deployment: buildkitd" "Rootless build engine for the rebuild path" "Kubernetes Deployment" {
                            buildkitInstance = softwareSystemInstance buildkit
                        }
                        blastRadius = infrastructureNode "Job: blast-radius" "Reads OCI annotations, answers the CVE-time query; stand-in for the org's observability stack" "regctl"
                    }
                    deploymentNode "namespace: registry" "lite overlay: registry:2  /  full overlay: Harbor" "Kubernetes Namespace" {
                        destInstance = softwareSystemInstance destRegistries
                    }
                }
            }

            deploymentNode "Internet / org network" "External to the cluster" {
                srcInstance = softwareSystemInstance sourceRegistries
                pkgInstance = softwareSystemInstance packageMirror
            }

            # Instance↔instance relationships (houba→source/dest/buildkit, buildkit→packageMirror)
            # are auto-replicated from the model; only the infrastructure-node edges are declared here.
            gitSync -> policyRepo "Pulls policies" "git"
            blastRadius -> destInstance "Reads provenance stamps" "regctl / API" "DataCoupling"
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
            include layCli layUc layDomain layPorts layAdapters config platformEng productTeam sourceRegistries destRegistries buildkit
            autolayout lr
        }

        component houbaCli "Component" "Inside the houba CLI: every fine-grained component of the hexagonal layers — cli, use cases, the pure domain (4 concerns), the ports, and the adapters that reach the external systems." {
            include *
            exclude layCli layUc layDomain layPorts layAdapters
            autolayout lr
        }

        deployment houba "Reference (kind)" "ReferenceDeployment" "The reference deployment: a kind cluster running houba as a CronJob, through to the blast-radius consumer. Doubles as the production blueprint." {
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
