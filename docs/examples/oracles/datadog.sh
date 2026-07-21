#!/usr/bin/env sh
# Reference usage oracle for `knock purge` (KNOCK_USAGE_ORACLE_CMD).
# Replaceable: knock owns the idle threshold; THIS script owns "what counts as prod".
# Contract: stdin = {"digest","image_ref","identity":{...},"since"}; stdout = {"last_seen": <ISO|null>}.
# Requires: DD_API_KEY, DD_APP_KEY, DD_SITE (e.g. datadoghq.eu), and `jq`.
set -eu
query="$(cat)"
digest="$(printf '%s' "$query" | jq -r .digest)"
since="$(printf '%s' "$query" | jq -r .since)"

# Datadog container data tags running images by image_id (the digest) and env.
# Find the most recent prod sighting of this exact digest since `since`.
# (Illustrative call — adapt the endpoint/metric to your Datadog setup. Must print one JSON object.)
resp="$(curl -sS -G "https://api.${DD_SITE}/api/v2/..." \
  -H "DD-API-KEY: ${DD_API_KEY}" -H "DD-APPLICATION-KEY: ${DD_APP_KEY}" \
  --data-urlencode "filter[query]=env:prod container.image_id:${digest}" \
  --data-urlencode "filter[from]=${since}")"

last="$(printf '%s' "$resp" | jq -r '.data[0].attributes.timestamp // empty')"
if [ -n "$last" ]; then
  printf '{"last_seen":"%s","detail":"prod sighting"}\n' "$last"
else
  printf '{"last_seen":null,"detail":"no prod sighting since %s"}\n' "$since"
fi
