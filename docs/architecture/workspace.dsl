workspace "houba" "Single front door / stamper for external container images." {

    model {
        platformEng = person "Platform / Security Engineer" "Owns the hardening policy and the registry roster; operates houba as the single front door for external images."
        productTeam = person "Product / Application Team" "Declares its imports as MirrorPolicy files and consumes the hardened, stamped images."
        incidentResponder = person "Incident Responder (SRE / Security)" "At CVE time, computes the blast-radius from houba's provenance stamp."

        houba = softwareSystem "houba" "Single front door / stamper: mirrors external container images, optionally rebuilds them through a hardening policy, and stamps them with standardized, portable provenance." "Target"

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
            relationship "Relationship" {
                routing Orthogonal
            }
            relationship "DataCoupling" {
                dashed true
            }
        }
    }

    configuration {
        scope landscape
    }
}
