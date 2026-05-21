# Phase A — image minimaliste. Phase B ajoute skopeo + buildctl + git.
FROM python:3.12-slim AS build

WORKDIR /src
COPY pyproject.toml uv.lock ./
COPY hub2hub ./hub2hub

RUN pip install --no-cache-dir uv && uv build

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

ENTRYPOINT ["h2h"]
CMD ["--help"]
