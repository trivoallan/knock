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
