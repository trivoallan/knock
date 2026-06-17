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

.PHONY: help reference docs-serve cluster image up-local local local-run \
        argocd demo demo-run openbao-seed seed-incident \
        blast-radius dt-bootstrap publish-sbom dt-vulns dt-ui registry-ui docker-auth logs down

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

registry-ui: ## Open Zot's built-in registry UI (port-forward svc/registry to localhost:8080)
	@echo ">> Browse the mirrored images at http://localhost:8080 (Ctrl-C to stop)."
	$(KUBECTL) -n $(NS) port-forward svc/registry 8080:5000

logs: ## Tail the last reconcile run's logs
	$(KUBECTL) -n $(NS) logs job/houba-reconcile-run -f

down: ## Delete the kind cluster
	kind delete cluster --name $(CLUSTER)
