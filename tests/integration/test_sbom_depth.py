"""Acceptance gate: the real buildkit-syft-scanner must surface every incident class at the
right granularity. Permanent guard against silent scanner-depth regression.

Heavyweight (docker + buildx + network for apt). Skipped unless docker buildx is available;
run locally / nightly. Mirrors the empirical matrix in the SBOM-generation spec (ADR 0029).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest


def _has_buildx() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "buildx", "version"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(not _has_buildx(), reason="needs docker buildx")

# Real vulnerable log4j-core 2.14.1 (the Log4Shell version), from Maven Central. A fabricated
# stub jar is NOT reliably cataloged through nesting — the real artifact is what the scanner reads.
_LOG4J_URL = (
    "https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-core/2.14.1/"
    "log4j-core-2.14.1.jar"
)


def _make_nested_log4j_jar(dst: Path) -> None:
    # Spring Boot fat-jar with the real log4j-core 2.14.1 nested under BOOT-INF/lib/ — the
    # actual Log4Shell shape (a transitive dep buried inside an application archive).
    inner = dst.parent / "log4j-core-2.14.1.jar"
    try:
        urllib.request.urlretrieve(_LOG4J_URL, inner)
    except (urllib.error.URLError, OSError) as e:
        pytest.skip(f"no network to fetch log4j from Maven Central: {e}")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        z.write(inner, "BOOT-INF/lib/log4j-core-2.14.1.jar")


def _spdx_package_names(oci_tar: Path) -> set[str]:
    names: set[str] = set()
    with tarfile.open(oci_tar) as tar:
        for m in tar.getmembers():
            if not m.isfile() or "blobs/sha256/" not in m.name:
                continue
            f = tar.extractfile(m)
            if f is None:
                continue
            try:
                obj = json.loads(f.read())
            except (ValueError, UnicodeDecodeError):
                continue
            if "spdx" in obj.get("predicateType", "").lower():
                doc = obj.get("predicate", obj)
            elif obj.get("spdxVersion"):
                doc = obj
            else:
                continue
            for p in doc.get("packages", []):
                names.add(p.get("name", ""))
    return names


def test_sbom_depth_incident_matrix(tmp_path: Path) -> None:
    ctx = tmp_path / "ctx"
    ctx.mkdir()
    _make_nested_log4j_jar(ctx / "app.jar")
    (ctx / "Dockerfile").write_text(
        "FROM debian:bookworm-slim\n"
        "COPY app.jar /opt/app.jar\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends openssl redis-server"
        " && rm -rf /var/lib/apt/lists/*\n"
        "RUN cp /bin/true /usr/local/bin/mongod && chmod +x /usr/local/bin/mongod\n"
    )
    out = tmp_path / "img.tar"
    r = subprocess.run(
        [
            "docker",
            "buildx",
            "build",
            "--sbom=true",
            "--provenance=false",
            "-o",
            f"type=oci,dest={out}",
            str(ctx),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if r.returncode != 0:
        # The plain `docker` buildx driver (default on CI runners) cannot emit attestations;
        # this gate needs the docker-container driver or the containerd image store. Skip rather
        # than fail there — it is a local/nightly depth guard, not a per-PR CI check. Any OTHER
        # build error is a real failure.
        if (
            "is not supported for the docker driver" in r.stderr
            or "Attestation is not supported" in r.stderr
        ):
            pytest.skip(f"buildx driver lacks attestation support: {r.stderr.strip()}")
        pytest.fail(f"buildx build failed:\n{r.stderr}")
    names = _spdx_package_names(out)

    # Present — each incident class captured at the right layer
    assert "log4j-core" in names, "Log4Shell: nested fat-JAR dependency not captured"
    assert "openssl" in names or "libssl3" in names, "Heartbleed: OS openssl not captured"
    assert "liblzma5" in names, "XZ: OS liblzma not captured"
    assert "redis-server" in names, "middleware-via-package not captured"

    # Absent — runtime (out of scope) + the documented bare-binary blind spot (kept visible)
    assert "runc" not in names, "Leaky Vessels: host runtime must not appear in an image SBOM"
    assert "mongod" not in names, "bare-binary middleware is the documented coverage blind spot"
