# Phase B+ — runtime image: Python CLI + buildctl (rebuild) + regctl (registry ops).

FROM python:3.13-alpine AS build

WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY houba ./houba

RUN pip install --no-cache-dir uv && uv build

FROM python:3.13-alpine AS runtime

# buildctl comes from the official upstream image (static Go binary).
COPY --from=moby/buildkit:v0.31.1 /usr/bin/buildctl /usr/bin/buildctl

# regctl is houba's registry client (list/copy/annotate/delete/login/registry-set).
COPY --from=regclient/regctl:v0.11.5 /regctl /usr/bin/regctl

# cosign signs the in-toto attestations on the rebuild path (HOUBA_ATTEST_*).
COPY --from=ghcr.io/sigstore/cosign/cosign:v3.1.1 /ko-app/cosign /usr/bin/cosign

# syft generates the package-level SBOM on both paths (HOUBA_SBOM_FORMATS).
COPY --from=anchore/syft:v1.45.1 /syft /usr/bin/syft

# bash: the demo/ops Jobs (reconcile helpers, blast-radius, publish-sbom, scan-attach, seed-incident)
# run bash scripts mounted into this image — Alpine ships only busybox sh, so add bash (regression
# from the Alpine runtime rebase). houba itself (Python) does not need it.
RUN apk add --no-cache ca-certificates bash

COPY --from=build /src/dist/*.whl /tmp/
# ponytail: musl test — if pydantic-core (Rust) / pyyaml (C) fall to source build
# here, add a builder stage with build-base+rust and copy the venv across.
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# scan-pipeline scripts talk to Redis Streams via redis-py (image-only; houba-core stays zero-new-dep)
RUN pip install --no-cache-dir "redis>=5.0"

# houba's own deployment runs hardened (runAsNonRoot + readOnlyRootFilesystem).
# Run as a NUMERIC non-root uid: kubelet can only satisfy runAsNonRoot from a
# numeric image USER (a username string is rejected), and the manifests set no
# runAsUser. HOME points at /tmp — the sole writable mount under a read-only
# root fs — so regctl/buildctl can write their config there.
ENV HOME=/tmp
USER 65532:65532

ENTRYPOINT ["houba"]
CMD ["--help"]
