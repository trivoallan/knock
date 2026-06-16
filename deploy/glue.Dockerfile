# The publish-sbom job's image: the houba runtime (regctl + python3) plus the syft binary,
# used ONLY to convert houba's SPDX SBOM to the CycloneDX that Dependency-Track ingests.
# Demo glue — deliberately separate from the product image so houba itself never ships syft.
ARG HOUBA_IMAGE=houba:dev
FROM anchore/syft:latest AS syft
FROM ${HOUBA_IMAGE}
COPY --from=syft /syft /usr/local/bin/syft
