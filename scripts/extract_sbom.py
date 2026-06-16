#!/usr/bin/env python3
"""Read a buildkit image index on stdin; write the embedded SPDX document to argv[1].

buildkit's `attest:sbom=true` attaches the SBOM as an attestation manifest in the OCI index:
a manifest annotated `vnd.docker.reference.type=attestation-manifest`, whose in-toto layer
(`in-toto.io/predicate-type: https://spdx.dev/Document`) wraps the SPDX in its `.predicate`.
Exits non-zero if no SBOM attestation is present (copy-only image).
"""
import json, os, subprocess, sys

out = sys.argv[1]
idx = json.load(sys.stdin)
ref = os.environ["DT_REF"]
repo = ref.rsplit(":", 1)[0]

manifests = idx.get("manifests", [])
att = [m for m in manifests
       if (m.get("annotations") or {}).get("vnd.docker.reference.type") == "attestation-manifest"]
if not att:
    sys.exit(1)

for m in att:
    mf = json.loads(subprocess.run(  # noqa: S603
        ["regctl", "manifest", "get", f"{repo}@{m['digest']}", "--format", "{{json .}}"],
        check=True, capture_output=True, text=True).stdout)
    for layer in mf.get("layers", []):
        if (layer.get("annotations") or {}).get("in-toto.io/predicate-type") == "https://spdx.dev/Document":
            blob = subprocess.run(  # noqa: S603
                ["regctl", "blob", "get", repo, layer["digest"]],
                check=True, capture_output=True, text=True).stdout
            spdx = json.loads(blob).get("predicate")
            if spdx:
                json.dump(spdx, open(out, "w"))
                sys.exit(0)
sys.exit(1)
