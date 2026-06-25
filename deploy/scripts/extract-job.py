#!/usr/bin/env python3
"""Extract one Job from a rendered kustomize stream, rename it, override BLAST_REPOS.

Usage: extract-job.py <source-job-name> <new-name> <blast-repos> < rendered.yaml > job.yaml
Used by `make demo-teams` to run a teams-scoped scan-attach over the two teams' repos.
"""

import sys

import yaml

src, new_name, blast = sys.argv[1], sys.argv[2], sys.argv[3]
for doc in yaml.safe_load_all(sys.stdin):
    if doc and doc.get("kind") == "Job" and doc.get("metadata", {}).get("name") == src:
        doc["metadata"]["name"] = new_name
        doc["metadata"].pop("resourceVersion", None)
        spec = doc["spec"]["template"]["spec"]
        for container in spec.get("containers", []):
            env = container.setdefault("env", [])
            env[:] = [e for e in env if e.get("name") != "BLAST_REPOS"]
            env.append({"name": "BLAST_REPOS", "value": blast})
        doc["spec"].pop("selector", None)
        labels = doc["spec"]["template"].setdefault("metadata", {}).setdefault("labels", {})
        labels.pop("controller-uid", None)
        labels.pop("batch.kubernetes.io/controller-uid", None)
        print(yaml.safe_dump(doc))
        sys.exit(0)
sys.exit(f"Job {src!r} not found in input")
