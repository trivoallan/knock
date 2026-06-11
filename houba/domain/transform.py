"""Pure transform domain: vocabulary validation, Dockerfile rendering, content versioning.

No I/O, no config import — the application layer resolves names to data and passes it in.
"""

from __future__ import annotations

import hashlib
import json

from houba.domain.mirror_policy import TransformStep
from houba.errors import PolicyValidationError

ALLOWED_STEPS = ("injectCA", "rewritePackageSources")


def validate_transform_steps(steps: list[TransformStep]) -> None:
    """Reject any step outside the known vocabulary or with malformed params."""
    for step in steps:
        if step.name not in ALLOWED_STEPS:
            raise PolicyValidationError(
                f"unknown transform step {step.name!r}; allowed: {list(ALLOWED_STEPS)}"
            )
        if step.name == "injectCA":
            certs = step.params.get("certs")
            if (
                not isinstance(certs, list)
                or not certs
                or not all(isinstance(c, str) for c in certs)
            ):
                raise PolicyValidationError(
                    "injectCA.certs must be a non-empty list of cert names (strings)"
                )
        elif step.name == "rewritePackageSources":
            mirror = step.params.get("mirror")
            if not isinstance(mirror, str) or not mirror:
                raise PolicyValidationError(
                    "rewritePackageSources.mirror must be a non-empty mirror name (string)"
                )


CA_DIR = "/usr/local/share/ca-certificates"


def render_dockerfile(
    source_ref: str,
    *,
    ca_cert_filenames: list[str],
    apt_mirror: str | None,
    apk_mirror: str | None,
) -> str:
    """Render a hardening Dockerfile. Canonical order: CA trust, then source rewrite
    (the two steps are independent). Package-source rewrite is a host-swap preserving
    the upstream path — v1 assumes a pull-through mirror at the given base URL."""
    lines = [f"FROM {source_ref}"]
    if ca_cert_filenames:
        lines.append(f"COPY {' '.join(ca_cert_filenames)} {CA_DIR}/")
        lines.append("RUN update-ca-certificates")
    rewrites: list[str] = []
    if apt_mirror:
        rewrites.append(
            f"if [ -f /etc/apt/sources.list ]; then "
            f"sed -ri 's#https?://[^/]+#{apt_mirror}#g' /etc/apt/sources.list; fi"
        )
        rewrites.append(
            f"if ls /etc/apt/sources.list.d/*.list >/dev/null 2>&1; then "
            f"sed -ri 's#https?://[^/]+#{apt_mirror}#g' /etc/apt/sources.list.d/*.list; fi"
        )
    if apk_mirror:
        rewrites.append(
            f"if [ -f /etc/apk/repositories ]; then "
            f"sed -ri 's#https?://[^/]+#{apk_mirror}#g' /etc/apk/repositories; fi"
        )
    if rewrites:
        lines.append("RUN set -eux; " + "; ".join(rewrites))
    return "\n".join(lines) + "\n"


def transform_version(
    steps: list[TransformStep],
    *,
    cert_contents: dict[str, str],
    apt_mirror: str | None,
    apk_mirror: str | None,
) -> str:
    """Content hash of the *resolved* transform. Changes when steps, cert bytes,
    or mirror URLs change — drives transform-aware change detection."""
    payload = {
        "steps": [[s.name, s.params] for s in steps],
        "certs": {k: cert_contents[k] for k in sorted(cert_contents)},
        "apt": apt_mirror,
        "apk": apk_mirror,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()
