# Phase B — image runtime : Python CLI + buildctl.

FROM python:3.12-slim AS build

WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY houba ./houba

RUN pip install --no-cache-dir uv && uv build

FROM python:3.12-slim AS runtime

# buildctl vient de l'image upstream officielle (binaire Go statique).
COPY --from=moby/buildkit:v0.30.0 /usr/bin/buildctl /usr/bin/buildctl

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

ENTRYPOINT ["houba"]
CMD ["--help"]
