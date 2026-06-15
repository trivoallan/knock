# houba reference deployment — local demo driver (kind).
# See docs/runbooks/reference-deployment.md for the full walkthrough.

CLUSTER ?= houba-demo
IMAGE   ?= houba:dev
NS      ?= houba

# The blast-radius script lives outside the base dir (canonical scripts/), so the
# configMapGenerator needs the relaxed load restrictor. `kubectl apply -k` can't pass
# it, so we render then apply.
KUSTOMIZE = kubectl kustomize --load-restrictor LoadRestrictionsNone
KUBECTL   = kubectl
# Overlay used by `blast-radius` (overridden by demo-transform). Default keeps demo-lite as-is.
OVERLAY  ?= deploy/overlays/local-lite

# ---- ArgoCD variant (App-of-Apps) ----------------------------------------
# The demo syncs the `demo` apps set from git; children are pulled by ArgoCD, not
# applied locally. To demo YOUR branch, push it to your fork and override these:
#   ARGOCD_REPO_URL=https://github.com/me/houba ARGOCD_REPO_REF=my-branch make demo-argocd
# ponytail: children are read from git (intrinsic App-of-Apps coupling) — uncommitted
# local changes are invisible until pushed; that is the documented ceiling, not a bug.
ARGOCD_REPO_URL ?= https://github.com/trivoallan/houba
ARGOCD_REPO_REF ?= main
ARGOCD_ENV      ?= demo
ARGOCD_VERSION  ?= v2.12.4

.PHONY: help cluster image up-lite demo-lite demo-lite-run \
        up-full demo-full demo-full-run \
        up-transform demo-transform demo-transform-run \
        argocd demo-argocd demo-argocd-run argocd-prod argocd-seed \
        blast-radius docker-auth logs down

help: ## List targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

cluster: ## Create the kind cluster if absent
	@kind get clusters 2>/dev/null | grep -qx $(CLUSTER) || kind create cluster --name $(CLUSTER)

image: ## Build the houba runtime image and load it into kind
	docker build -t $(IMAGE) .
	kind load docker-image $(IMAGE) --name $(CLUSTER)

# ---- LITE (copy path, registry:2) ----------------------------------------
up-lite: cluster image ## Bring up the lite stack (no run yet)
	$(KUSTOMIZE) deploy/overlays/local-lite | $(KUBECTL) apply -f -

demo-lite: up-lite demo-lite-run ## Lite stack + one reconcile + report
	@sleep 3
	$(MAKE) blast-radius

demo-lite-run: ## Fire a one-shot reconcile from the suspended CronJob
	-$(KUBECTL) -n $(NS) delete job houba-reconcile-run --ignore-not-found
	$(KUBECTL) -n $(NS) create job houba-reconcile-run --from=cronjob/houba-reconcile
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-reconcile-run --timeout=300s

# ---- FULL (rebuild path, Harbor) -----------------------------------------
up-full: cluster image ## Bring up the full stack (Harbor installed separately — see overlay README)
	$(KUSTOMIZE) deploy/overlays/local-full | $(KUBECTL) apply -f -

demo-full-run: ## Fire a one-shot hardening reconcile
	-$(KUBECTL) -n $(NS) delete job houba-reconcile-run --ignore-not-found
	$(KUBECTL) -n $(NS) create job houba-reconcile-run --from=cronjob/houba-reconcile
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-reconcile-run --timeout=600s

# ---- TRANSFORM (rebuild path, no Harbor) ----------------------------------
up-transform: cluster image ## Bring up the transform stack (buildkitd, throwaway registry, no Harbor)
	$(KUSTOMIZE) deploy/overlays/local-transform | $(KUBECTL) apply -f -
	$(KUBECTL) -n $(NS) rollout status deploy/buildkitd --timeout=180s

demo-transform: up-transform demo-transform-run ## Transform stack + one rebuild reconcile + report
	@sleep 3
	$(MAKE) blast-radius OVERLAY=deploy/overlays/local-transform

demo-transform-run: ## Fire a one-shot rebuild reconcile (setTimezone variants)
	-$(KUBECTL) -n $(NS) delete job houba-reconcile-run --ignore-not-found
	$(KUBECTL) -n $(NS) create job houba-reconcile-run --from=cronjob/houba-reconcile
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-reconcile-run --timeout=600s

# ---- ARGOCD (App-of-Apps variant) ----------------------------------------
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

demo-argocd: cluster image argocd ## App-of-Apps demo: sync the `demo` apps set from git, then reconcile + report
	ARGOCD_REPO_URL=$(ARGOCD_REPO_URL) ARGOCD_REPO_REF=$(ARGOCD_REPO_REF) ARGOCD_ENV=$(ARGOCD_ENV) \
	  envsubst < deploy/argocd/root.yaml | $(KUBECTL) apply -f -
	@echo ">> Waiting for ArgoCD to sync the demo children from $(ARGOCD_REPO_URL)@$(ARGOCD_REPO_REF) ..."
	@until $(KUBECTL) -n $(NS) get deploy/registry >/dev/null 2>&1; do sleep 5; done
	$(KUBECTL) -n $(NS) rollout status deploy/registry --timeout=300s
	@until $(KUBECTL) -n $(NS) get cronjob/houba-reconcile >/dev/null 2>&1; do sleep 5; done
	$(MAKE) demo-argocd-run
	@sleep 3
	# Re-run blast-radius from the SAME manifests ArgoCD syncs (not the default
	# local-lite overlay) so it doesn't fight selfHeal on the cronjob suspend field.
	$(MAKE) blast-radius OVERLAY=deploy/argocd/sources/houba-demo

demo-argocd-run: ## Fire a one-shot reconcile from the ArgoCD-synced CronJob
	-$(KUBECTL) -n $(NS) delete job houba-reconcile-run --ignore-not-found
	$(KUBECTL) -n $(NS) create job houba-reconcile-run --from=cronjob/houba-reconcile
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-reconcile-run --timeout=300s

argocd-prod: cluster image argocd ## Bring up the FULL prod App-of-Apps on kind (ESO+KEDA+Prometheus+OpenBao operators, then houba+buildkitd) + seed dev OpenBao
	ARGOCD_REPO_URL=$(ARGOCD_REPO_URL) ARGOCD_REPO_REF=$(ARGOCD_REPO_REF) ARGOCD_ENV=prod \
	  envsubst < deploy/argocd/root.yaml | $(KUBECTL) apply -f -
	@echo ">> Prod App-of-Apps applied. ArgoCD is syncing 6 children: operators (wave 0) then houba+buildkitd (wave 1)."
	@echo ">> Waiting for OpenBao (wave 0) to come up so it can be seeded ..."
	@for i in $$(seq 1 60); do \
	  $(KUBECTL) -n openbao get pod -l app.kubernetes.io/name=openbao 2>/dev/null | grep -q Running && break; \
	  sleep 10; \
	done
	-$(MAKE) argocd-seed
	@echo ">> Done. Watch the rollout with:  kubectl get applications -n argocd"
	@echo ">> NOTE: the policy front door defaults to the bundled busybox example (git-sync'd from this repo),"
	@echo ">>       so houba reconciles a REAL policy. The remaining gap for a live mirror is a destination"
	@echo ">>       registry: the prod apps set deploys none, and the seeded roster points at an in-cluster"
	@echo ">>       registry that isn't there. So this target demonstrates the GitOps BOOTSTRAP (operators +"
	@echo ">>       ESO->OpenBao secret path + a real policy), not a completed push. Point the roster at your"
	@echo ">>       registry (or sync the demo 'registry' app) for a working reconcile. See the runbook."

argocd-seed: ## Seed the dev OpenBao so ESO can resolve houba-registries (placeholder roster; demo only)
	$(KUBECTL) -n openbao create secret generic openbao-token --from-literal=token=root --dry-run=client -o yaml | $(KUBECTL) apply -f -
	$(KUBECTL) -n openbao exec -i $$($(KUBECTL) -n openbao get pod -l app.kubernetes.io/name=openbao -o jsonpath='{.items[0].metadata.name}') -- sh -c 'BAO_ADDR=http://127.0.0.1:8200 BAO_TOKEN=root bao kv put secret/houba/registries HOUBA_REGISTRIES='\''{"local":{"host":"registry.houba.svc.cluster.local:5000","tls_verify":false}}'\'''

# ---- consumer / ops ------------------------------------------------------
blast-radius: ## (Re)run the blast-radius consumer and print its report
	-$(KUBECTL) -n $(NS) delete job houba-blast-radius --ignore-not-found
	$(KUSTOMIZE) $(OVERLAY) | $(KUBECTL) apply -f - >/dev/null
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-blast-radius --timeout=120s
	$(KUBECTL) -n $(NS) logs job/houba-blast-radius

docker-auth: ## Seed source-registry creds (set DOCKER_USER + DOCKER_PASS) so pulls authenticate (avoids rate limits)
	@test -n "$$DOCKER_USER" && test -n "$$DOCKER_PASS" || \
	  { echo "ERROR: set DOCKER_USER and DOCKER_PASS (a Docker Hub username + access token)"; exit 1; }
	@printf '{"auths":{"https://index.docker.io/v1/":{"auth":"%s"}}}' \
	  "$$(printf '%s:%s' "$$DOCKER_USER" "$$DOCKER_PASS" | base64 | tr -d '\n')" \
	  | $(KUBECTL) -n $(NS) create secret generic houba-docker-config \
	      --from-file=config.json=/dev/stdin --dry-run=client -o yaml | $(KUBECTL) apply -f -

logs: ## Tail the last reconcile run's logs
	$(KUBECTL) -n $(NS) logs job/houba-reconcile-run -f

down: ## Delete the kind cluster
	kind delete cluster --name $(CLUSTER)
