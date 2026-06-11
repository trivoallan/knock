workspace "houba" "Single front door / stamper for external container images." {

    model {
        platformEng = person "Platform / Security Engineer" "Owns the hardening policy, operates houba, and mandates it as the single front door for external images."
        productTeam = person "Product / Application Team" "Declares its products (properties.yml) and consumes the hardened, stamped images."
        incidentResponder = person "Incident Responder (SRE / Security)" "At CVE time, computes the blast-radius from houba's provenance stamp."

        houba = softwareSystem "houba" "Single front door / stamper: rebuilds external container images through a hardening policy and stamps them with standardized, portable provenance." "Target"

        sourceRegistries = softwareSystem "Source Registries" "External public OCI registries (Docker Hub, Quay, GHCR) the images originate from." "External"
        buildkit = softwareSystem "BuildKit" "OCI build engine driven by houba to rebuild and harden images." "External"
        harbor = softwareSystem "Harbor" "The organization's private OCI registry; destination for the stamped images." "External"
        gitlab = softwareSystem "GitLab" "Hosts the product declarations; houba proposes changes to them via merge request." "External"
        teams = softwareSystem "Microsoft Teams" "Receives run notifications." "External"
        observability = softwareSystem "Observability / CMDB" "The organization's existing query stack; reads the provenance stamp to answer blast-radius questions during an incident." "External,Downstream"

        platformEng -> houba "Configures the hardening policy, runs / schedules imports" "CLI"
        productTeam -> gitlab "Declares its products (properties.yml)" "Git / Web"
        houba -> gitlab "Clones declarations, proposes changes via merge request, reads project variables" "git + REST"
        houba -> sourceRegistries "Lists tags, inspects digests, pulls images" "skopeo"
        houba -> buildkit "Submits the hardening build (internal CA, package mirrors)" "buildctl"
        houba -> harbor "Reads state; pushes stamped images, tags, labels, immutable rules" "Harbor REST v2 + push"
        houba -> teams "Sends run notifications" "webhook"
        productTeam -> harbor "Pulls the hardened images" "docker pull (OCI)"
        observability -> harbor "Reads provenance stamps on images" "scan / API" "DataCoupling"
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
