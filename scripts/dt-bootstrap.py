#!/usr/bin/env python3
"""dt-bootstrap — read DT's default Automation API key and write it to the dt-api-key Secret.

DT's Automation team ships with BOM_UPLOAD + PROJECT_CREATION and a pre-generated key. This
waits for the API, logs in as the default admin (handling the forced first-login password
change), reads the Automation key, and PUTs it into a k8s Secret via the in-cluster API using
the pod's ServiceAccount token. No kubectl, no curl — stdlib only (the houba image has python3).
"""
import json, os, ssl, time, urllib.parse, urllib.request

DT = os.environ.get("DT_URL", "http://dependency-track-apiserver:8080")
NS = os.environ.get("POD_NAMESPACE", "houba")
NEW_PW = os.environ.get("DT_ADMIN_PASSWORD", "houba-demo-admin")
SA = "/var/run/secrets/kubernetes.io/serviceaccount"


def _post_form(path, **fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(DT + path, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    return urllib.request.urlopen(req, timeout=15)  # noqa: S310


def wait_api():
    for i in range(60):
        try:
            urllib.request.urlopen(DT + "/api/version", timeout=5)  # noqa: S310
            return
        except Exception:
            print(f"» waiting for DT API ({i}) ...", flush=True)
            time.sleep(5)
    raise SystemExit("DT API never became ready")


def login():
    try:
        return _post_form("/api/v1/user/login", username="admin", password="admin").read().decode()
    except urllib.error.HTTPError:
        # forced password change on first login
        _post_form("/api/v1/user/forceChangePassword", username="admin", password="admin",
                   newPassword=NEW_PW, confirmPassword=NEW_PW)
        return _post_form("/api/v1/user/login", username="admin", password=NEW_PW).read().decode()


def automation_key(jwt):
    req = urllib.request.Request(DT + "/api/v1/team", headers={"Authorization": f"Bearer {jwt}"})
    teams = json.load(urllib.request.urlopen(req, timeout=15))  # noqa: S310
    for t in teams:
        if t.get("name") == "Automation":
            for k in t.get("apiKeys") or []:
                return k["key"]
    raise SystemExit("no Automation API key found in DT")


def write_secret(key):
    token = open(f"{SA}/token").read().strip()
    api = f"https://{os.environ['KUBERNETES_SERVICE_HOST']}:{os.environ['KUBERNETES_SERVICE_PORT']}"
    ctx = ssl.create_default_context(cafile=f"{SA}/ca.crt")
    body = json.dumps({
        "apiVersion": "v1", "kind": "Secret", "metadata": {"name": "dt-api-key"},
        "stringData": {"DT_API_KEY": key},
    }).encode()
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{api}/api/v1/namespaces/{NS}/secrets"
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=body, headers=hdr, method="POST"), context=ctx, timeout=15)  # noqa: S310
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise
        urllib.request.urlopen(urllib.request.Request(f"{url}/dt-api-key", data=body, headers=hdr, method="PUT"), context=ctx, timeout=15)  # noqa: S310
    print("» dt-api-key Secret written", flush=True)


if __name__ == "__main__":
    wait_api()
    write_secret(automation_key(login()))
