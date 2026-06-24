# houba reference deployment — local driver (kind).
# See docs/how-to/reference-deployment.md for the full walkthrough.
#
#   make demo    the single Argo reference on kind (operators + ESO->OpenBao +
#                buildkitd + the reference policy + registry + reconcile + report)
#   make local   the inner-loop escape hatch (kubectl apply -k, no Argo/operators)

CLUSTER ?= houba-demo
IMAGE   ?= houba:dev
NS      ?= houba
COSIGN  ?= cosign
HELM    ?= helm

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

# ---- Operator versions (pinned to the versions proven on this cluster) ----
# cert-manager must be installed before kargo (kargo depends on cert-manager webhooks).
CERT_MANAGER_VERSION ?= v1.20.2
KARGO_VERSION        ?= 1.10.7
KYVERNO_VERSION      ?= 3.8.1

# ---- Demo registry + UV shorthand ----------------------------------------
# DEMO_REG is the in-CLUSTER service name — what the kubelet/Kyverno see in a Pod's
# image ref. The host can't resolve it (kind has no port mapping), so host-side
# regctl/houba calls reach the registry through a `port-forward svc/registry` to
# DEMO_REG_LOCAL (the proven bridge, same as incident-deploy / registry-ui).
DEMO_REG       ?= registry.houba.svc.cluster.local:5000
DEMO_REG_LOCAL ?= localhost:5000
UV             ?= uv

# ---- log4shell incident image (pinned digest) ----------------------------
# CVE-2021-44228 (log4j 2.14.1, Critical) confirmed via grype on 2026-06-24.
# Source is a Docker schema2 manifest; the demo Zot is OCI-strict (rejects it with
# HTTP 415), so seed-log4shell converts to OCI on the way in (regctl image mod --to-oci).
LOG4SHELL_SRC ?= ghcr.io/christophetd/log4shell-vulnerable-app@sha256:6f88430688108e512f7405ac3c73d47f5c370780b94182854ea2cddc6bd59929

.PHONY: help reference docs-serve cluster image up-local local local-run \
        argocd cert-manager kargo kyverno \
        demo demo-run openbao-seed seed-incident incident-deploy seed-log4shell \
        blast-radius dt-bootstrap publish-sbom dt-vulns dt-ui registry-ui argocd-ui docker-auth logs down \
        scan cosign-keygen demo-assert-gates

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

argocd-ui: ## Open the ArgoCD UI (port-forward svc/argocd-server; prints admin creds)
	@PW=$$($(KUBECTL) -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null \
	      | python3 -c 'import base64,sys; sys.stdout.write(base64.b64decode(sys.stdin.read()).decode())'); \
	  test -n "$$PW" || { echo "ERROR: argocd-initial-admin-secret not found — run 'make demo' (or 'make argocd') first"; exit 1; }; \
	  echo ">> ArgoCD UI at https://localhost:8083  (login admin / $$PW — self-signed cert, accept the warning). Ctrl-C to stop."
	$(KUBECTL) -n argocd port-forward svc/argocd-server 8083:443

cert-manager: ## Install cert-manager ($(CERT_MANAGER_VERSION)) — prerequisite for kargo
	@$(KUBECTL) get namespace cert-manager >/dev/null 2>&1 \
	  && $(HELM) status cert-manager -n cert-manager >/dev/null 2>&1 \
	  && echo ">> cert-manager already installed — skipping" \
	  || $(HELM) upgrade --install cert-manager jetstack/cert-manager \
	       --repo https://charts.jetstack.io \
	       --namespace cert-manager --create-namespace \
	       --version $(CERT_MANAGER_VERSION) \
	       --set crds.enabled=true
	$(KUBECTL) -n cert-manager rollout status deploy/cert-manager --timeout=180s
	$(KUBECTL) -n cert-manager rollout status deploy/cert-manager-webhook --timeout=180s

kargo: cert-manager ## Install kargo ($(KARGO_VERSION)) — promotion gate operator (requires helm 3.12+, not helm 4+)
	@# kargo chart is published as oci://ghcr.io/akuity/kargo — requires helm 3.12+ (helm 4 has a
	@# breaking OCI-descriptor check incompatible with kargo's chart format as of v1.10.x).
	@$(KUBECTL) get namespace kargo >/dev/null 2>&1 \
	  && $(HELM) status kargo -n kargo >/dev/null 2>&1 \
	  && echo ">> kargo already installed — skipping" \
	  || $(HELM) upgrade --install kargo oci://ghcr.io/akuity/kargo \
	       --namespace kargo --create-namespace \
	       --version v$(KARGO_VERSION) \
	       --set api.adminAccount.passwordHash='$$2a$$10$$Zrhhie4vDfMTQ4l4l7e6.eRZ90rQ7P2dZ2NfMA8RHk0HhB6Sa9Ki' \
	       --set api.adminAccount.tokenSigningKey=demotokensigningkeyabc123
	$(KUBECTL) -n kargo rollout status deploy/kargo-api --timeout=300s

kyverno: ## Install kyverno ($(KYVERNO_VERSION)) — admission gate operator (standalone, no cert-manager dep)
	@$(KUBECTL) get namespace kyverno >/dev/null 2>&1 \
	  && $(HELM) status kyverno -n kyverno >/dev/null 2>&1 \
	  && echo ">> kyverno already installed — skipping" \
	  || $(HELM) upgrade --install kyverno kyverno/kyverno \
	       --repo https://kyverno.github.io/kyverno \
	       --namespace kyverno --create-namespace \
	       --version $(KYVERNO_VERSION)
	$(KUBECTL) -n kyverno rollout status deploy/kyverno-admission-controller --timeout=300s

demo: cluster image argocd cert-manager kargo kyverno ## The single Argo reference on kind, end-to-end (operators + ESO->OpenBao + reference policy + registry + reconcile + report)
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
	$(MAKE) cosign-keygen
	$(MAKE) demo-run
	@sleep 3
	$(MAKE) blast-radius OVERLAY=deploy/argocd/sources/houba
	$(MAKE) dt-bootstrap OVERLAY=deploy/argocd/sources/houba
	$(MAKE) publish-sbom OVERLAY=deploy/argocd/sources/houba
	$(MAKE) scan OVERLAY=deploy/argocd/sources/houba
	$(MAKE) seed-log4shell
	@echo ">> Beat 3a (project teams): kargo holds the log4shell freight (houba verify exit 1)."
	@echo ">> Beat 3b (platform team): Kyverno denies the log4shell pod at admission."
	@echo ">> Beat 4: the rebuilt clean image is promoted and DT blast-radius goes green."
	$(MAKE) demo-assert-gates
	@echo ">> The Argo reference is up and mirrored the reference policy end-to-end: operators"
	@echo ">>       (cert-manager + kargo + kyverno + ESO->OpenBao) + houba/buildkitd, the"
	@echo ">>       ESO->OpenBao secret path, a git-sync'd policy (busybox copy + debian rebuild),"
	@echo ">>       the kargo promotion gate (beat 3a), the Kyverno admission gate (beat 3b),"
	@echo ">>       and DT blast-radius (beat 4)."
	@echo ">>       For a REAL cluster: pin your published image, point sources/houba at your"
	@echo ">>       policy repo and vault, and use your registry (not this demo registry)."
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

cosign-keygen: ## Generate a demo cosign keypair and load it as a Secret (key-mode signing)
	@test -f /tmp/houba-demo.key || COSIGN_PASSWORD= $(COSIGN) generate-key-pair --output-key-prefix /tmp/houba-demo
	-$(KUBECTL) -n $(NS) delete secret houba-attest-key --ignore-not-found
	$(KUBECTL) -n $(NS) create secret generic houba-attest-key \
	  --from-file=cosign.key=/tmp/houba-demo.key \
	  --from-file=cosign.pub=/tmp/houba-demo.pub \
	  --from-literal=COSIGN_PASSWORD=

seed-log4shell: ## Copy the pinned log4shell image into the demo registry (beat-3 vuln source)
	@# Host can't resolve the in-cluster registry name, so push via a port-forward to
	@# DEMO_REG_LOCAL. Source is Docker schema2; Zot is OCI-strict (HTTP 415) → convert on copy.
	@$(KUBECTL) -n $(NS) port-forward svc/registry 5000:5000 >/dev/null 2>&1 & \
	  PF=$$!; trap 'kill $$PF 2>/dev/null' EXIT; \
	  for i in $$(seq 1 20); do curl -fsS http://$(DEMO_REG_LOCAL)/v2/ >/dev/null 2>&1 && break; sleep 0.5; done; \
	  regctl image mod $(LOG4SHELL_SRC) --to-oci --create $(DEMO_REG_LOCAL)/demo/log4shell:1
	@echo ">> Seeded demo/log4shell:1 — raw, intentionally never scanned/attested; that missing verdict is exactly what the gates catch (beats 3a/3b)."

demo-assert-gates: ## Self-check beats 3a/3b (kargo gate + Kyverno admission) and beat 4 (DT clear)
	@test -f /tmp/houba-demo.pub || { echo "ERROR: /tmp/houba-demo.pub missing — run 'make cosign-keygen' first"; exit 1; }
	@# prod is a throwaway scratch namespace for the admission probe (not the kargo 'prod' Stage CR).
	@$(KUBECTL) create namespace prod --dry-run=client -o yaml | $(KUBECTL) apply -f - >/dev/null
	@# Host-side regctl/houba reach the registry via a port-forward (DEMO_REG_LOCAL); the digest
	@# is identical to the in-cluster ref. Beat 3b's `kubectl run` keeps the in-cluster name
	@# (DEMO_REG) — Kyverno matches that string and denies at admission, before any image pull.
	@$(KUBECTL) -n $(NS) port-forward svc/registry 5000:5000 >/dev/null 2>&1 & \
	  PF=$$!; trap 'kill $$PF 2>/dev/null' EXIT; \
	  for i in $$(seq 1 20); do curl -fsS http://$(DEMO_REG_LOCAL)/v2/ >/dev/null 2>&1 && break; sleep 0.5; done; \
	  D=$$(regctl image digest $(DEMO_REG_LOCAL)/demo/log4shell:1); \
	  echo ">> Beat 3a: kargo gate must HOLD log4shell (houba verify exit 1)"; \
	  HOUBA_ATTEST_SIGNER=key HOUBA_ATTEST_KEY_REF=/tmp/houba-demo.pub \
	    $(UV) run houba verify $(DEMO_REG_LOCAL)/demo/log4shell@$$D --require scan-pass --max-severity critical; \
	  RC=$$?; \
	  test $$RC -eq 1 || { echo "BEAT3a FAIL: gate did not hold log4shell (exit $$RC)"; exit 1; }; \
	  echo ">> Beat 3b: Kyverno must DENY the log4shell pod at admission"; \
	  $(KUBECTL) -n prod run l4s --image=$(DEMO_REG)/demo/log4shell@$$D --restart=Never 2>/dev/null \
	    && { echo "BEAT3b FAIL: admission did not deny"; exit 1; } || echo "   denied (ok)"; \
	  echo ">> Beats 3a/3b asserted."
	$(UV) run python3 deploy/scripts/dt_assert_clear.py CVE-2021-44228
