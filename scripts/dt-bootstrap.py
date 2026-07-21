#!/usr/bin/env python3
"""dt-bootstrap — give the publish Job a working Dependency-Track API key.

DT ships with admin/admin but FORCES a password change before the API is usable (login returns
401 until the default password is changed), and the default Automation team has no API key until
one is generated. This handles both, idempotently across reruns:

  1. ensure the admin password is NEW_PW — log in if it already is, else force-change the default
     admin/admin first (a fresh DT requires it),
  2. log in as admin for a JWT,
  3. find the Automation team, ensure it has BOM_UPLOAD + PROJECT_CREATION_UPLOAD, and mint a
     fresh API key for it,
  4. write the key into the dt-api-key Secret via the in-cluster k8s API.

stdlib only — the knock image has python3, no kubectl/curl. Every step logs so a failure in the
DT auth dance is diagnosable from `kubectl logs job/knock-dt-bootstrap`.
"""

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

DT = os.environ.get("DT_URL", "http://dependency-track-apiserver:8080")
NS = os.environ.get("POD_NAMESPACE", "knock")
NEW_PW = os.environ.get("DT_ADMIN_PASSWORD", "knock-demo-admin")
SA = "/var/run/secrets/kubernetes.io/serviceaccount"


def _req(method, path, *, jwt=None, form=None, json_body=None):
    data, headers = None, {}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    req = urllib.request.Request(DT + path, data=data, method=method, headers=headers)
    return urllib.request.urlopen(req, timeout=20)


def wait_api():
    for i in range(60):
        try:
            _req("GET", "/api/version")
            return
        except Exception:
            print(f"» waiting for DT API ({i}) ...", flush=True)
            time.sleep(5)
    raise SystemExit("DT API never became ready")


def jwt_token():
    # Idempotent: if the password is already NEW_PW, just log in; otherwise force-change the
    # default admin/admin (a fresh DT requires it before the API is usable), then log in.
    try:
        tok = (
            _req("POST", "/api/v1/user/login", form={"username": "admin", "password": NEW_PW})
            .read()
            .decode()
        )
        print("» logged in (password already set)", flush=True)
        return tok
    except urllib.error.HTTPError as e:
        if e.code != 401:
            raise
    print("» forcing the default admin password change ...", flush=True)
    try:
        _req(
            "POST",
            "/api/v1/user/forceChangePassword",
            form={
                "username": "admin",
                "password": "admin",
                "newPassword": NEW_PW,
                "confirmPassword": NEW_PW,
            },
        )
    except urllib.error.HTTPError as e:
        # already changed (or rejected) — fall through and let the login below be the real check
        print(f"» forceChangePassword returned {e.code}, continuing to login ...", flush=True)
    tok = (
        _req("POST", "/api/v1/user/login", form={"username": "admin", "password": NEW_PW})
        .read()
        .decode()
    )
    print("» logged in", flush=True)
    return tok


def automation_key(jwt):
    teams = json.load(_req("GET", "/api/v1/team", jwt=jwt))
    auto = next((t for t in teams if t.get("name") == "Automation"), None)
    if auto is None:
        raise SystemExit("no Automation team in DT")
    uuid = auto["uuid"]
    # Ensure the team can upload + auto-create projects (the default set varies by DT version);
    # granting an already-held permission is a harmless no-op.
    for perm in ("BOM_UPLOAD", "PROJECT_CREATION_UPLOAD", "VIEW_PORTFOLIO"):
        try:
            _req("POST", f"/api/v1/permission/{perm}/team/{uuid}", jwt=jwt)
            print(f"» granted {perm} to Automation", flush=True)
        except urllib.error.HTTPError as e:
            print(f"» grant {perm} returned {e.code} (already held?)", flush=True)
    # Generate a FRESH key — recent DT masks existing keys in GET responses, so a reused key
    # 401s on upload. The PUT returns the full, usable key once.
    print("» generating a fresh Automation API key ...", flush=True)
    created = json.load(_req("PUT", f"/api/v1/team/{uuid}/key", jwt=jwt))
    return created["key"]


def write_secret(key):
    token = open(f"{SA}/token").read().strip()
    api = f"https://{os.environ['KUBERNETES_SERVICE_HOST']}:{os.environ['KUBERNETES_SERVICE_PORT']}"
    ctx = ssl.create_default_context(cafile=f"{SA}/ca.crt")
    data = json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "dt-api-key"},
            "stringData": {"DT_API_KEY": key},
        }
    ).encode()
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{api}/api/v1/namespaces/{NS}/secrets"
    try:
        urllib.request.urlopen(
            urllib.request.Request(url, data=data, headers=hdr, method="POST"),
            context=ctx,
            timeout=15,
        )
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise
        urllib.request.urlopen(
            urllib.request.Request(f"{url}/dt-api-key", data=data, headers=hdr, method="PUT"),
            context=ctx,
            timeout=15,
        )
    print("» dt-api-key Secret written", flush=True)


def enable_osv(jwt):
    # OSV is keyless; DT stores the enabled ecosystems as a ';'-separated list in a single
    # `google.osv.enabled` property (e.g. 'Debian;Alpine' — Debian is on by default). Ensure
    # 'Debian' is present (idempotent). The mirror itself only runs on the next DT restart
    # (`make dt-vulns`); enabling the ecosystem alone does nothing without that.
    props = json.load(_req("GET", "/api/v1/configProperty", jwt=jwt))
    osv = next((p for p in props if p.get("propertyName") == "google.osv.enabled"), None)
    if osv is None:
        print("» google.osv.enabled not found — enable OSV Debian in the UI", flush=True)
        return
    ecosystems = [e for e in (osv.get("propertyValue") or "").split(";") if e]
    if "Debian" in ecosystems:
        print(
            f"» OSV Debian already enabled ({';'.join(ecosystems)!r}); mirror runs on restart",
            flush=True,
        )
        return
    ecosystems.append("Debian")
    body = [
        {
            "groupName": osv["groupName"],
            "propertyName": "google.osv.enabled",
            "propertyValue": ";".join(ecosystems),
        }
    ]
    _req("POST", "/api/v1/configProperty/aggregate", jwt=jwt, json_body=body)
    print(f"» enabled OSV ecosystem 'Debian' ({';'.join(ecosystems)!r})", flush=True)


if __name__ == "__main__":
    wait_api()
    jwt = jwt_token()
    enable_osv(jwt)
    write_secret(automation_key(jwt))
