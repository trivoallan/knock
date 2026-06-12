# Phase B+ — runtime image: Python CLI + buildctl (rebuild) + regctl (registry ops).

FROM python:3.12-slim AS build

WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY houba ./houba

RUN pip install --no-cache-dir uv && uv build

FROM python:3.12-slim AS runtime

# buildctl comes from the official upstream image (static Go binary).
COPY --from=moby/buildkit:v0.30.0 /usr/bin/buildctl /usr/bin/buildctl

# regctl is houba's registry client (list/copy/annotate/delete/login/registry-set).
COPY --from=regclient/regctl:v0.11.5 /regctl /usr/bin/regctl

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

ENTRYPOINT ["houba"]
CMD ["--help"]
