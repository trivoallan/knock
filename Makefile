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

.PHONY: help cluster image up-lite demo-lite demo-lite-run \
        up-full demo-full demo-full-run blast-radius logs down

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

# ---- consumer / ops ------------------------------------------------------
blast-radius: ## (Re)run the blast-radius consumer and print its report
	-$(KUBECTL) -n $(NS) delete job houba-blast-radius --ignore-not-found
	$(KUSTOMIZE) deploy/overlays/local-lite | $(KUBECTL) apply -f - >/dev/null
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-blast-radius --timeout=120s
	$(KUBECTL) -n $(NS) logs job/houba-blast-radius

logs: ## Tail the last reconcile run's logs
	$(KUBECTL) -n $(NS) logs job/houba-reconcile-run -f

down: ## Delete the kind cluster
	kind delete cluster --name $(CLUSTER)
