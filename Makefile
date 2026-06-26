# houba reference deployment — local driver (kind).
# See docs/how-to/reference-deployment.md for the full walkthrough.
#
#   make demo    the single Argo reference on kind (operators + ESO->OpenBao +
#                buildkitd + the reference policy + registry + reconcile + report)
#   make local   the inner-loop escape hatch (kubectl apply -k, no Argo/operators)

CLUSTER ?= houba-demo
IMAGE   ?= houba:dev
NS      ?= houba

# The blast-radius script lives outside the base dir (canonical scripts/), so the
# configMapGenerator needs the relaxed load restrictor. `kubectl apply -k` can't pass
# it, so we render then apply.
KUSTOMIZE = kubectl kustomize --load-restrictor LoadRestrictionsNone
KUBECTL   = kubectl
# Overlay used by `blast-radius` (overridden by `demo` to the Argo source). Defaults to
# the local overlay so a bare `make blast-radius` matches `make local`.
OVERLAY  ?= deploy/overlays/local

# ---- Argo reference (App-of-Apps) ----------------------------------------
# `make demo` applies root.yaml; ArgoCD pulls the children from git. To demo YOUR branch,
# push it to your fork and override:
#   ARGOCD_REPO_URL=https://github.com/me/houba ARGOCD_REPO_REF=my-branch make demo
# ponytail: children are read from git (intrinsic App-of-Apps coupling) — uncommitted
# local changes are invisible until pushed. `make local` is the escape hatch for that.
ARGOCD_REPO_URL ?= https://github.com/trivoallan/houba
ARGOCD_REPO_REF ?= main
ARGOCD_VERSION  ?= v2.12.4
# The OpenBao server pod (StatefulSet -> openbao-0). Selected by name pattern, NOT a
# chart label (which varies): the `-[0-9]+$$` anchor matches openbao-0 while excluding
# the agent-injector / csi-provider pods the chart also creates.
OPENBAO_POD = $$($(KUBECTL) -n openbao get pod -o name | grep -E 'openbao-[0-9]+$$' | head -1)

# Host-side port-forward address for the local Zot (registry svc/registry 5000).
# Used by demo-mongobleed and any host-side regctl/houba invocation.
LOCAL_REG ?= localhost:5000
# HOUBA_REGISTRIES roster for host-side access (port-forward to the local Zot).
LOCAL_HOUBA_REGISTRIES ?= {"local":{"host":"$(LOCAL_REG)","tls_verify":false}}

.PHONY: help reference docs-serve cluster image up-local up-brownfield local local-run \
        argocd demo demo-run openbao-seed seed-incident incident-deploy \
        blast-radius dt-bootstrap publish-sbom dt-vulns dt-ui registry-ui argocd-ui docker-auth logs down \
        demo-mongobleed

help: ## List targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

reference: ## Regenerate docs/reference/ (policy + config + CLI) from the schemas and Typer app
	uv run --group docs python scripts/gen_reference.py

docs-serve: ## Serve the Docusaurus docs site locally (hot reload)
	cd website && npm install && npm start

cluster: ## Create the kind cluster if absent
	@kind get clusters 2>/dev/null | grep -qx $(CLUSTER) || kind create cluster --name $(CLUSTER)

image: ## Build the houba runtime image and load it into kind
	docker build -t $(IMAGE) .
	kind load docker-image $(IMAGE) --name $(CLUSTER)

# ---- LOCAL (inner-loop escape hatch: copy + rebuild, no Argo) -------------
up-local: cluster image ## Bring up the local stack (buildkitd + throwaway registry)
	$(KUSTOMIZE) deploy/overlays/local | $(KUBECTL) apply -f -
	$(KUBECTL) -n $(NS) rollout status deploy/buildkitd --timeout=180s

up-brownfield: cluster image ## Bring up the lean brownfield stack (registry + buildkitd; no scan-pipeline/DT — KEDA-free, so it deploys on a bare cluster / in CI)
	$(KUSTOMIZE) deploy/overlays/local-brownfield | $(KUBECTL) apply -f -
	$(KUBECTL) -n $(NS) rollout status deploy/registry --timeout=180s
	$(KUBECTL) -n $(NS) rollout status deploy/buildkitd --timeout=180s

local: up-local ## Local stack + reconcile + bootstrap DT + publish SBOMs + report
	$(MAKE) seed-incident
	$(MAKE) local-run
	@sleep 3
	$(MAKE) dt-bootstrap
	$(MAKE) publish-sbom
	$(MAKE) blast-radius
	@echo ">> SBOMs published to Dependency-Track. Browse them with 'make dt-ui'."

local-run: ## Fire a one-shot reconcile from the suspended CronJob
	-$(KUBECTL) -n $(NS) delete job houba-reconcile-run --ignore-not-found
	$(KUBECTL) -n $(NS) create job houba-reconcile-run --from=cronjob/houba-reconcile
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-reconcile-run --timeout=600s

# ---- DEMO (the single Argo reference on kind) ----------------------------
argocd: ## Install argo-cd into the kind cluster + relax the kustomize load restrictor
	$(KUBECTL) create namespace argocd --dry-run=client -o yaml | $(KUBECTL) apply -f -
	$(KUBECTL) apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/$(ARGOCD_VERSION)/manifests/install.yaml
	# base references scripts/blast-radius.sh outside deploy/ — ArgoCD's kustomize build
	# needs the relaxed restrictor (global build option; not settable per-Application).
	$(KUBECTL) -n argocd patch configmap argocd-cm --type merge \
	  -p '{"data":{"kustomize.buildOptions":"--load-restrictor LoadRestrictionsNone"}}'
	$(KUBECTL) -n argocd rollout restart deploy/argocd-repo-server
	$(KUBECTL) -n argocd rollout status deploy/argocd-repo-server --timeout=180s
	$(KUBECTL) -n argocd rollout status deploy/argocd-server --timeout=180s

argocd-ui: ## Open the ArgoCD UI (port-forward svc/argocd-server; prints admin creds)
	@PW=$$($(KUBECTL) -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null \
	      | python3 -c 'import base64,sys; sys.stdout.write(base64.b64decode(sys.stdin.read()).decode())'); \
	  test -n "$$PW" || { echo "ERROR: argocd-initial-admin-secret not found — run 'make demo' (or 'make argocd') first"; exit 1; }; \
	  echo ">> ArgoCD UI at https://localhost:8083  (login admin / $$PW — self-signed cert, accept the warning). Ctrl-C to stop."
	$(KUBECTL) -n argocd port-forward svc/argocd-server 8083:443

demo: cluster image argocd ## The single Argo reference on kind, end-to-end (operators + ESO->OpenBao + reference policy + registry + reconcile + report)
	ARGOCD_REPO_URL=$(ARGOCD_REPO_URL) ARGOCD_REPO_REF=$(ARGOCD_REPO_REF) \
	  envsubst < deploy/argocd/root.yaml | $(KUBECTL) apply -f -
	@echo ">> App-of-Apps applied. ArgoCD is syncing 4 children: ESO+OpenBao (wave 0) then houba+buildkitd (wave 1)."
	@echo ">> Waiting for the OpenBao server pod (wave 0) to be Running so it can be seeded ..."
	@for i in $$(seq 1 60); do \
	  P=$(OPENBAO_POD); \
	  [ -n "$$P" ] && $(KUBECTL) -n openbao get $$P -o jsonpath='{.status.phase}' 2>/dev/null | grep -q Running && break; \
	  sleep 10; \
	done
	-$(MAKE) openbao-seed
	@echo ">> Deploying Zot — the push destination + built-in UI (host registry.houba.svc.cluster.local:5000)."
	@echo ">>       Applied out-of-band; ArgoCD does not manage it. Browse it with 'make registry-ui'."
	$(KUSTOMIZE) deploy/argocd/sources/registry | $(KUBECTL) apply -f -
	$(KUBECTL) -n $(NS) rollout status deploy/registry --timeout=180s
	$(MAKE) seed-incident
	@echo ">> Waiting for ESO to materialize the houba-registries Secret from OpenBao ..."
	@for i in $$(seq 1 30); do $(KUBECTL) -n $(NS) get secret houba-registries >/dev/null 2>&1 && break; sleep 10; done
	@echo ">> Waiting for the houba CronJob (wave 1) to sync ..."
	@for i in $$(seq 1 60); do $(KUBECTL) -n $(NS) get cronjob/houba-reconcile >/dev/null 2>&1 && break; sleep 10; done
	$(MAKE) demo-run
	@sleep 3
	$(MAKE) blast-radius OVERLAY=deploy/argocd/sources/houba
	$(MAKE) dt-bootstrap OVERLAY=deploy/argocd/sources/houba
	$(MAKE) publish-sbom OVERLAY=deploy/argocd/sources/houba
	@echo ">> The Argo reference is up and mirrored the reference policy end-to-end: operators"
	@echo ">>       (ESO+OpenBao) + houba/buildkitd, the ESO->OpenBao secret path, a git-sync'd"
	@echo ">>       policy (busybox copy + debian rebuild), and the registry destination."
	@echo ">>       For a REAL cluster: pin your published image, point sources/houba at your"
	@echo ">>       policy repo and vault, and use your registry (not this demo registry:2)."
	@echo ">> Browse the ArgoCD UI with 'make argocd-ui' (admin creds printed)."

demo-run: ## Fire a one-shot reconcile from the ArgoCD-synced CronJob
	-$(KUBECTL) -n $(NS) delete job houba-reconcile-run --ignore-not-found
	$(KUBECTL) -n $(NS) create job houba-reconcile-run --from=cronjob/houba-reconcile
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-reconcile-run --timeout=600s

openbao-seed: ## Seed the dev OpenBao so ESO can resolve houba-registries (placeholder roster; demo only)
	$(KUBECTL) -n openbao create secret generic openbao-token --from-literal=token=root --dry-run=client -o yaml | $(KUBECTL) apply -f -
	$(KUBECTL) -n openbao exec -i $(OPENBAO_POD) -- sh -c 'BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=root bao kv put secret/houba/registries HOUBA_REGISTRIES='\''{"local":{"host":"registry.houba.svc.cluster.local:5000","tls_verify":false}}'\'''

# ---- consumer / ops ------------------------------------------------------
seed-incident: ## Build the xz fixture IN-CLUSTER (buildkitd) → upstream/ + bypassed/ repos in the Zot
	$(KUBECTL) -n $(NS) rollout status deploy/buildkitd --timeout=180s
	$(KUBECTL) -n $(NS) rollout status deploy/registry --timeout=120s
	-$(KUBECTL) -n $(NS) delete job houba-seed-incident --ignore-not-found
	$(KUSTOMIZE) $(OVERLAY) | $(KUBECTL) apply -f - >/dev/null
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-seed-incident --timeout=600s
	$(KUBECTL) -n $(NS) logs job/houba-seed-incident

incident-deploy: ## Run the marked runtime stand-in (pause pods carrying the placed/bypass digest)
	@echo ">> resolving placed + bypass digests from the in-cluster Zot ..."
	$(KUBECTL) -n $(NS) port-forward svc/registry 5000:5000 >/dev/null 2>&1 & \
	  PF_PID=$$!; \
	  trap 'kill $$PF_PID 2>/dev/null' EXIT; \
	  for i in $$(seq 1 20); do curl -fsS http://localhost:5000/v2/ >/dev/null 2>&1 && break; sleep 0.5; done; \
	  PLACED_DIGEST=$$(curl -s -o /dev/null -D - \
	      -H 'Accept: application/vnd.oci.image.index.v1+json' \
	      -H 'Accept: application/vnd.docker.distribution.manifest.list.v2+json' \
	      http://localhost:5000/v2/demo/debian-xz/manifests/5.6.1 \
	    | tr -d '\r' | awk -F': ' 'tolower($$1)=="docker-content-digest"{print $$2}'); \
	  BYPASS_DIGEST=$$(curl -s -o /dev/null -D - \
	      -H 'Accept: application/vnd.oci.image.index.v1+json' \
	      -H 'Accept: application/vnd.docker.distribution.manifest.list.v2+json' \
	      http://localhost:5000/v2/bypassed/debian-xz/manifests/5.6.1 \
	    | tr -d '\r' | awk -F': ' 'tolower($$1)=="docker-content-digest"{print $$2}'); \
	  test -n "$$PLACED_DIGEST" || { echo "ERROR: could not resolve demo/debian-xz:5.6.1 — run 'make seed-incident' + a reconcile first"; exit 1; }; \
	  test -n "$$BYPASS_DIGEST" || { echo "ERROR: could not resolve bypassed/debian-xz:5.6.1 — run 'make seed-incident' first"; exit 1; }; \
	  echo ">> placed=$$PLACED_DIGEST  bypass=$$BYPASS_DIGEST"; \
	  sed -e "s|\$${PLACED_DIGEST}|$$PLACED_DIGEST|g" -e "s|\$${BYPASS_DIGEST}|$$BYPASS_DIGEST|g" \
	      deploy/incidents/incident-workloads.yaml.tmpl | $(KUBECTL) apply -f -
	$(KUBECTL) -n team-a rollout status deploy/debian-xz --timeout=120s
	$(KUBECTL) -n team-b rollout status deploy/debian-xz --timeout=120s
	$(KUBECTL) -n team-c rollout status deploy/debian-xz-bypassed --timeout=120s
	@echo ">> marked workloads running. Re-run 'make blast-radius' to see the RUNNING IN column."

blast-radius: ## (Re)run the blast-radius consumer and print its report
	-$(KUBECTL) -n $(NS) delete job houba-blast-radius --ignore-not-found
	$(KUSTOMIZE) $(OVERLAY) | $(KUBECTL) apply -f - >/dev/null
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-blast-radius --timeout=120s
	$(KUBECTL) -n $(NS) logs job/houba-blast-radius

dt-bootstrap: ## Mint DT's API key into the dt-api-key Secret (re-runnable)
	-$(KUBECTL) -n $(NS) delete job houba-dt-bootstrap --ignore-not-found
	$(KUSTOMIZE) $(OVERLAY) | $(KUBECTL) apply -f - >/dev/null
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-dt-bootstrap --timeout=300s
	$(KUBECTL) -n $(NS) logs job/houba-dt-bootstrap

publish-sbom: ## Convert each rebuilt image's SBOM to CycloneDX and upload it to Dependency-Track
	-$(KUBECTL) -n $(NS) delete job houba-publish-sbom --ignore-not-found
	$(KUSTOMIZE) $(OVERLAY) | $(KUBECTL) apply -f - >/dev/null
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-publish-sbom --timeout=300s
	$(KUBECTL) -n $(NS) logs job/houba-publish-sbom

dt-vulns: ## Trigger DT's OSV (Debian) vuln mirror — restart the apiserver (data persists on the PVC)
	@echo ">> dt-bootstrap enables the OSV Debian ecosystem; the mirror only runs on restart. Restarting ..."
	$(KUBECTL) -n $(NS) rollout restart deploy/dependency-track-apiserver
	$(KUBECTL) -n $(NS) rollout status deploy/dependency-track-apiserver --timeout=300s
	@echo ">> OSV Debian mirror now running in the background (a few minutes). Then re-run 'make publish-sbom'"
	@echo ">>       to re-analyze the projects; CVEs then show in 'make dt-ui'."

dt-ui: ## Open the Dependency-Track UI (frontend on :8080, apiserver on :8081 — both needed)
	@echo ">> DT UI at http://localhost:8080  (login admin / $${DT_ADMIN_PASSWORD:-houba-demo-admin} — set by dt-bootstrap). Ctrl-C to stop."
	$(KUBECTL) -n $(NS) port-forward svc/dependency-track-apiserver 8081:8080 & \
	  $(KUBECTL) -n $(NS) port-forward svc/dependency-track-frontend 8080:8080

docker-auth: ## Seed source-registry creds (set DOCKER_USER + DOCKER_PASS) so pulls authenticate (avoids rate limits)
	@test -n "$$DOCKER_USER" && test -n "$$DOCKER_PASS" || \
	  { echo "ERROR: set DOCKER_USER and DOCKER_PASS (a Docker Hub username + access token)"; exit 1; }
	@printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}}}' \
	  "$$(printf '%s:%s' "$$DOCKER_USER" "$$DOCKER_PASS" | base64 | tr -d '\n')" \
	  | $(KUBECTL) -n $(NS) create secret generic houba-docker-config \
	      --from-file=config.json=/dev/stdin --dry-run=client -o yaml | $(KUBECTL) apply -f -

registry-ui: ## Open Zot's built-in registry UI (port-forward svc/registry to localhost:8082)
	@echo ">> Browse the mirrored images at http://localhost:8082 (Ctrl-C to stop)."
	$(KUBECTL) -n $(NS) port-forward svc/registry 8082:5000

logs: ## Tail the last reconcile run's logs
	$(KUBECTL) -n $(NS) logs job/houba-reconcile-run -f

down: ## Delete the kind cluster
	kind delete cluster --name $(CLUSTER)

scan: ## Run the scan-attach Job (grype on the SBOM -> houba attach) over the placed images
	-$(KUBECTL) -n $(NS) delete job houba-scan-attach --ignore-not-found
	$(KUSTOMIZE) $(OVERLAY) | $(KUBECTL) apply -f - >/dev/null
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-scan-attach --timeout=300s
	$(KUBECTL) -n $(NS) logs job/houba-scan-attach --all-containers

# ---- BROWNFIELD DEMO ---------------------------------------------------------
# Demonstrates the mongobleed gap (CVE-2025-14847): grype + trivy both miss it
# on the official `mongo` image; the package-level SBOM inventory catches it.
# Act 1: houba reconcile copies mongo:8.0.15+8.0.16 with stamp + SBOM, then
#         demo-mongobleed.sh shows the scanner blind spot vs. the SBOM query.
# Act 2: demo-gate.sh runs grype on the XZ image and shows houba attach blocking it.
#
# Reconcile strategy: run `houba reconcile docs/examples/brownfield` directly on the
# host against the port-forwarded Zot (LOCAL_REG=localhost:5000). This sidesteps the
# in-cluster CronJob's fixed POLICY_DIR without mutating the shared houba-config
# ConfigMap — consistent with how the demo scripts themselves access the registry.
demo-mongobleed: OVERLAY = deploy/overlays/local-brownfield
demo-mongobleed: up-brownfield seed-incident ## Brownfield demo end-to-end: mongo corpus → Act 1 (scanner blind spot) + Act 2 (XZ gate)
	@echo ">> port-forwarding the local Zot to $(LOCAL_REG) for host-side reconcile + demo scripts …"
	$(KUBECTL) -n $(NS) port-forward svc/registry 5000:5000 >/dev/null 2>&1 & \
	  PF_PID=$$!; \
	  trap 'kill $$PF_PID 2>/dev/null' EXIT; \
	  for i in $$(seq 1 20); do \
	    python3 -c "import urllib.request; urllib.request.urlopen('http://$(LOCAL_REG)/v2/')" \
	      >/dev/null 2>&1 && break; sleep 0.5; \
	  done; \
	  echo ">> reconciling docs/examples/brownfield (copy path: mongo:8.0.15 + 8.0.16 → $(LOCAL_REG)/demo/mongo) …"; \
	  HOUBA_REGISTRIES='$(LOCAL_HOUBA_REGISTRIES)' \
	    HOUBA_SBOM_FORMATS='["spdx-json","cyclonedx-json"]' \
	    uv run houba reconcile docs/examples/brownfield; \
	  echo ">> Act 1 — scanner blind spot vs. the SBOM inventory"; \
	  REG=$(LOCAL_REG) scripts/demo-mongobleed.sh; \
	  echo ">> Act 2 — the front door blocks a vulnerable image at intake"; \
	  REG=$(LOCAL_REG) HOUBA_REGISTRIES='$(LOCAL_HOUBA_REGISTRIES)' HOUBA='uv run houba' \
	    scripts/demo-gate.sh
