# demo fixture — DELIBERATELY VULNERABLE (CVE-2024-3094, the XZ backdoor). Built ONLY to be
# rebuilt + inventoried by knock: it represents an external upstream image that shipped the
# backdoored xz. The payload is inert here — it only triggers in a running sshd→systemd→liblzma
# path, which this static image never executes. Built from public Debian archives.
FROM debian:sid
# Install the backdoored xz-utils 5.6.1-1 and matching liblzma5 directly from the
# snapshot.debian.org pool (packages present from ~2024-03-28 for all Debian architectures).
# We install via dpkg rather than apt because the sid index had already been superseded
# by 5.6.1+really5.4.5-1 (the emergency revert) at snapshot capture time.
# curl fetches the debs; it is removed afterwards to keep the layer lean.
ARG SNAPSHOT_BASE=http://snapshot.debian.org/archive/debian/20240328T120000Z/pool/main/x/xz-utils
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && ARCH=$(dpkg --print-architecture) \
 && curl -fSL "${SNAPSHOT_BASE}/liblzma5_5.6.1-1_${ARCH}.deb" -o /tmp/liblzma5.deb \
 && curl -fSL "${SNAPSHOT_BASE}/xz-utils_5.6.1-1_${ARCH}.deb" -o /tmp/xz-utils.deb \
 && dpkg -i /tmp/liblzma5.deb /tmp/xz-utils.deb \
 && rm /tmp/liblzma5.deb /tmp/xz-utils.deb \
 && apt-get purge -y --autoremove curl \
 && dpkg-query -W xz-utils    # prints: xz-utils\t5.6.1-1
LABEL org.opencontainers.image.description="demo fixture — deliberately vulnerable, CVE-2024-3094 (xz-utils 5.6.1-1)"
