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
# Policy repo ref the `demo-teams` reconcile git-syncs for docs/examples/teams. Defaults to main
# (the merged state); override to a feature branch to test before merge.
TEAMS_POLICY_REF ?= main
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
ROLLOUTS_VERSION     ?= 2.41.0   # argo-rollouts chart (app v1.9.0): the AnalysisTemplate CRD the kargo gate needs

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
        argocd cert-manager kargo kyverno argo-rollouts \
        demo demo-run openbao-seed seed-incident incident-deploy seed-log4shell \
        blast-radius dt-bootstrap publish-sbom dt-vulns dt-ui registry-ui kargo-ui argocd-ui docker-auth logs down \
        scan cosign-keygen demo-assert-gates demo-cve-blast-radius demo-teams

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
	  || $(HELM) upgrade --install cert-manager cert-manager \
	       --repo https://charts.jetstack.io \
	       --namespace cert-manager --create-namespace \
	       --version $(CERT_MANAGER_VERSION) \
	       --set crds.enabled=true
	$(KUBECTL) -n cert-manager rollout status deploy/cert-manager --timeout=180s
	$(KUBECTL) -n cert-manager rollout status deploy/cert-manager-webhook --timeout=180s

kargo: cert-manager ## Install kargo ($(KARGO_VERSION)) — promotion gate operator (requires helm 3.13+)
	@# The kargo Helm CHART lives at oci://ghcr.io/akuity/kargo-charts/kargo (tags carry no `v`);
	@# oci://ghcr.io/akuity/kargo is the container IMAGE (a multi-arch index) — pulling that as a
	@# chart fails with "manifest does not contain minimum number of descriptors". The chart pulls
	@# fine under both helm 3 and helm 4.
	@$(KUBECTL) get namespace kargo >/dev/null 2>&1 \
	  && $(HELM) status kargo -n kargo >/dev/null 2>&1 \
	  && echo ">> kargo already installed — skipping" \
	  || $(HELM) upgrade --install kargo oci://ghcr.io/akuity/kargo-charts/kargo \
	       --namespace kargo --create-namespace \
	       --version $(KARGO_VERSION) \
	       --set api.adminAccount.passwordHash='$$2b$$10$$V3i/1rDaLYm4Dhp5wiP8NOKbMgaHvfIAB2tIGbnwygGQbHWGYGIeq' \
	       --set api.adminAccount.tokenSigningKey=demotokensigningkeyabc123 \
	       --set api.rollouts.logs.enabled=true \
	       --set-string 'api.rollouts.logs.urlTemplate=http://kargo-loglens.houba.svc.cluster.local/$${{jobNamespace}}/$${{jobName}}/$${{container}}'
	@# api.rollouts.logs points kargo's AnalysisRun log view at the in-cluster `kargo-loglens`
	@# proxy (deploy/components/kargo-loglens), which serves a gate Job's pod logs by job-name —
	@# kargo streams logs "out of band" and won't read pod logs directly. Apply loglens separately
	@# (it lives in the houba namespace): `kubectl apply -f deploy/components/kargo-loglens/`.
	@# passwordHash above is bcrypt("houba-demo-admin") — the password `make kargo-ui` prints.
	@# Same demo password as DT (DT_ADMIN_PASSWORD); keep the two in sync if you change it.
	$(KUBECTL) -n kargo rollout status deploy/kargo-api --timeout=300s

kyverno: ## Install kyverno ($(KYVERNO_VERSION)) — admission gate operator (standalone, no cert-manager dep)
	@$(KUBECTL) get namespace kyverno >/dev/null 2>&1 \
	  && $(HELM) status kyverno -n kyverno >/dev/null 2>&1 \
	  && echo ">> kyverno already installed — skipping" \
	  || $(HELM) upgrade --install kyverno kyverno \
	       --repo https://kyverno.github.io/kyverno \
	       --namespace kyverno --create-namespace \
	       --version $(KYVERNO_VERSION)
	$(KUBECTL) -n kyverno rollout status deploy/kyverno-admission-controller --timeout=300s

argo-rollouts: ## Install Argo Rollouts ($(ROLLOUTS_VERSION)) — the AnalysisTemplate CRD + controller the kargo gate runs through
	@# The kargo scan-gate is an Argo Rollouts AnalysisTemplate (argoproj.io/v1alpha1); without
	@# this CRD `make seed-incident` fails to apply the kargo Component ("no matches for kind
	@# AnalysisTemplate"). Documented prerequisite (same posture as ESO), installed here so the
	@# one-command demo is self-contained on a fresh cluster.
	@$(KUBECTL) get namespace argo-rollouts >/dev/null 2>&1 \
	  && $(HELM) status argo-rollouts -n argo-rollouts >/dev/null 2>&1 \
	  && echo ">> argo-rollouts already installed — skipping" \
	  || $(HELM) upgrade --install argo-rollouts argo-rollouts \
	       --repo https://argoproj.github.io/argo-helm \
	       --namespace argo-rollouts --create-namespace \
	       --version $(ROLLOUTS_VERSION) \
	       --set installCRDs=true
	$(KUBECTL) -n argo-rollouts rollout status deploy/argo-rollouts --timeout=300s

demo: cluster image argocd cert-manager argo-rollouts kargo kyverno ## The single Argo reference on kind, end-to-end (operators + ESO->OpenBao + reference policy + registry + reconcile + report)
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

kargo-ui: ## Open the kargo UI to watch the promotion gate (port-forward svc/kargo-api)
	@# kargo-api serves the UI over HTTPS (self-signed, cert-manager-issued) on :443 — the same
	@# port the kargo quickstart port-forwards. The admin password is the bcrypt plaintext the
	@# `kargo` target installs (houba-demo-admin), the same as DT's.
	@echo ">> kargo UI at https://localhost:8084  (login admin / houba-demo-admin — self-signed cert, accept the warning). Ctrl-C to stop."
	$(KUBECTL) -n kargo port-forward svc/kargo-api 8084:443

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
	@# Beat 3a (live): the same verdict, but as a real kargo AnalysisRun. The reference Warehouse
	@# tracks log4shell and auto-promotes dev→prod (projectconfig.yaml), so prod's verification
	@# fires the houba-scan-gate Job and HOLDS the freight. Assert the prod Stage settled into
	@# Verified=VerificationFailed — the live gate's verdict, visible in the kargo UI (make kargo-ui).
	@echo ">> Beat 3a (live): kargo prod Stage must HOLD log4shell via its AnalysisRun"
	@for i in $$(seq 1 60); do \
	  V=$$($(KUBECTL) -n $(NS) get stage prod -o jsonpath='{range .status.conditions[?(@.type=="Verified")]}{.reason}{end}' 2>/dev/null); \
	  test "$$V" = "VerificationFailed" && { echo "   held (prod Verified=VerificationFailed)"; break; }; \
	  test $$i -eq 60 && { echo "BEAT3a-live FAIL: prod Stage did not hold log4shell in time (Verified=$$V)"; $(KUBECTL) -n $(NS) get stage prod; exit 1; }; \
	  sleep 5; \
	done
	@# Beat 4: package-level blast-radius. The host-side script reaches DT through a
	@# port-forward (the service name is unresolvable from the host) and authenticates with
	@# the Automation key dt-bootstrap minted into the dt-api-key Secret. We assert the
	@# log4shell component (log4j-core) is absent from every DT project — pure SBOM data,
	@# no vuln mirror needed.
	@$(KUBECTL) -n $(NS) port-forward svc/dependency-track-apiserver 8081:8080 >/dev/null 2>&1 & \
	  PF=$$!; trap 'kill $$PF 2>/dev/null' EXIT; \
	  for i in $$(seq 1 30); do curl -fsS http://localhost:8081/api/version >/dev/null 2>&1 && break; sleep 0.5; done; \
	  KEY=$$($(KUBECTL) -n $(NS) get secret dt-api-key -o jsonpath='{.data.DT_API_KEY}' | base64 -d); \
	  echo ">> Beat 4: DT blast-radius must be clear of log4shell (log4j-core)"; \
	  DT_BASE_URL=http://localhost:8081 DT_API_KEY=$$KEY \
	    $(UV) run python3 deploy/scripts/dt_assert_clear.py log4j-core

demo-cve-blast-radius: ## (opt-in, best-effort) Show DT's CVE→image blast radius for the XZ CVE
	@# The CVE-to-image leg of the XZ story (docs/examples/reference/debian-xz/DEMO.md), as an
	@# opt-in probe — NOT part of `make demo`, which stays deterministic via the component check.
	@# It mirrors the OSV Debian feed, re-analyses the placed images, then polls DT for projects
	@# flagged with CVE-2024-3094. The OSV mirror + DT re-analysis are async, so this is
	@# best-effort: it reports whatever DT knows and never fails (see dt_blast_radius_cve.py).
	$(MAKE) dt-vulns
	$(MAKE) publish-sbom OVERLAY=deploy/argocd/sources/houba
	@$(KUBECTL) -n $(NS) port-forward svc/dependency-track-apiserver 8081:8080 >/dev/null 2>&1 & \
	  PF=$$!; trap 'kill $$PF 2>/dev/null' EXIT; \
	  for i in $$(seq 1 30); do curl -fsS http://localhost:8081/api/version >/dev/null 2>&1 && break; sleep 0.5; done; \
	  KEY=$$($(KUBECTL) -n $(NS) get secret dt-api-key -o jsonpath='{.data.DT_API_KEY}' | base64 -d); \
	  DT_BASE_URL=http://localhost:8081 DT_API_KEY=$$KEY \
	    $(UV) run python3 deploy/scripts/dt_blast_radius_cve.py CVE-2024-3094 420

demo-teams: ## (opt-in) Two teams, each its OWN kargo Project (own namespace) with multiple images
	@# Additive, off the critical `make demo` path. Each team is a folder of MirrorPolicies
	@# (docs/examples/teams/{platform,data}) AND its own kargo Project (team-platform / team-data
	@# namespaces), gating MULTIPLE images: platform owns busybox+alpine (both clean → promote);
	@# data owns debian-xz+debian (both critical → held). Reconciles the folder, scan-attaches all
	@# four repos so each gate verdict is real, applies the per-team Projects + per-namespace gate
	@# infra, then asserts the contrast both host-side and via the live kargo gates.
	$(MAKE) seed-incident OVERLAY=$(OVERLAY)
	@# Reconcile the whole teams folder (the policy loader recurses subdirs → all four policies).
	-$(KUBECTL) -n $(NS) delete job houba-reconcile-teams --ignore-not-found
	@# POLICY_DIR points the reconcile at the teams folder; TEAMS_POLICY_REF lets you test from a
	@# branch before the folder is merged to the policy repo ref the cluster git-syncs (default main).
	$(KUBECTL) -n $(NS) create job houba-reconcile-teams --from=cronjob/houba-reconcile --dry-run=client -o yaml \
	  | $(KUBECTL) set env --local -f - POLICY_DIR=/policies/current/docs/examples/teams POLICY_REPO_REF=$(TEAMS_POLICY_REF) -o yaml \
	  | $(KUBECTL) apply -f -
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-reconcile-teams --timeout=600s
	@# scan-attach over ALL FOUR team repos so each image gets a real grype verdict (clean vs
	@# critical), not "no attestation". Extract just the scan-attach Job, override BLAST_REPOS.
	-$(KUBECTL) -n $(NS) delete job houba-scan-attach-teams --ignore-not-found
	$(KUSTOMIZE) $(OVERLAY) \
	  | $(UV) run python deploy/scripts/extract-job.py houba-scan-attach houba-scan-attach-teams "platform/busybox platform/alpine data/debian-xz data/debian" \
	  | $(KUBECTL) apply -f -
	$(KUBECTL) -n $(NS) wait --for=condition=complete job/houba-scan-attach-teams --timeout=300s
	@# loglens (cluster-scoped RBAC) makes each Project's gate AnalysisRun logs viewable in the UI.
	$(KUBECTL) apply -f deploy/components/kargo-loglens/
	@# Per-team kargo Projects: own namespace + Project + Warehouses (one per image) + dev→prod
	@# pipelines + auto-promotion, isolated from each other and from the reference `houba` Project.
	$(KUBECTL) apply -f deploy/components/kargo-teams/
	@# Each Project runs its gate Jobs in its OWN namespace, so replicate the gate infra there: the
	@# houba-scan-gate AnalysisTemplate + the public attest key + the registry roster Secret.
	@for ns in team-platform team-data; do \
	  $(KUBECTL) -n $$ns apply -f deploy/components/kargo/analysistemplate-scan-gate.yaml; \
	  for s in houba-attest-key houba-registries; do \
	    $(KUBECTL) -n $(NS) get secret $$s -o yaml \
	      | grep -vE '^  (namespace|resourceVersion|uid|creationTimestamp):' \
	      | $(KUBECTL) -n $$ns apply -f -; \
	  done; \
	done
	@# Assert the contrast host-side (deterministic, same engine the gate runs) across all 4 images.
	@test -f /tmp/houba-demo.pub || { echo "ERROR: /tmp/houba-demo.pub missing — run 'make cosign-keygen' first"; exit 1; }
	@$(KUBECTL) -n $(NS) port-forward svc/registry 5000:5000 >/dev/null 2>&1 & \
	  PF=$$!; trap 'kill $$PF 2>/dev/null' EXIT; \
	  for i in $$(seq 1 20); do curl -fsS http://$(DEMO_REG_LOCAL)/v2/ >/dev/null 2>&1 && break; sleep 0.5; done; \
	  for spec in "platform/busybox:1.37.0 0 platform" "platform/static:latest 0 platform" "data/debian-xz:5.6.1 1 data" "data/debian:bookworm-slim 1 data"; do \
	    set -- $$spec; ref=$$1; want=$$2; team=$$3; \
	    D=$$(regctl image digest $(DEMO_REG_LOCAL)/$$ref); \
	    HOUBA_ATTEST_SIGNER=key HOUBA_ATTEST_KEY_REF=/tmp/houba-demo.pub HOUBA_ATTEST_ALLOW_INSECURE_REGISTRY=true \
	      $(UV) run houba verify $(DEMO_REG_LOCAL)/$${ref%%:*}@$$D --require scan-pass --max-severity critical; \
	    rc=$$?; \
	    test $$rc -eq $$want || { echo "FAIL: $$ref (team $$team) expected verify exit $$want, got $$rc"; exit 1; }; \
	    test $$want -eq 0 && echo "   $$ref ($$team) PROMOTABLE (clean)" || echo "   $$ref ($$team) HELD (critical)"; \
	  done; \
	  echo ">> Host-side contrast holds across 4 images (platform clean / data critical)."
	@# Live kargo gates: each Project's prod Stages must reach the expected verdict (promoted/held).
	@echo ">> Live kargo gates per Project (auto-promotion fires each AnalysisRun):"
	@for spec in "team-platform busybox-prod True" "team-platform static-prod True" "team-data debian-xz-prod VerificationFailed" "team-data debian-prod VerificationFailed"; do \
	  set -- $$spec; ns=$$1; st=$$2; want=$$3; \
	  for i in $$(seq 1 60); do \
	    got=$$($(KUBECTL) -n $$ns get stage $$st -o jsonpath='{range .status.conditions[?(@.type=="Verified")]}{.status}/{.reason}{end}' 2>/dev/null); \
	    case "$$want" in \
	      True) case "$$got" in True/*) echo "   $$ns/$$st PROMOTED ($$got)"; break;; esac ;; \
	      *) case "$$got" in */VerificationFailed) echo "   $$ns/$$st HELD ($$got)"; break;; esac ;; \
	    esac; \
	    test $$i -eq 60 && { echo "FAIL: $$ns/$$st did not reach $$want (got '$$got')"; $(KUBECTL) -n $$ns get stage $$st; exit 1; }; \
	    sleep 5; \
	  done; \
	done
	@echo ">> Two kargo Projects, each gating multiple images: platform PROMOTED / data HELD, owner-attributed."
