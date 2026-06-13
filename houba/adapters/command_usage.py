"""Generic usage-oracle adapter: run an operator-supplied command, JSON over stdio.

houba stays on its subprocess-or-stdlib grain — no HTTP, no backend SDK in-tree.
"Datadog" is one such command (an example script). Contract:
  stdin  <- {"digest","image_ref","identity":{policy,import,variant},"since"}
  stdout -> {"last_seen": <ISO-8601> | null, "detail"?: str}
  exit 0 = answered; non-zero / timeout / bad stdout => UsageOracleError (fail-closed).
"""

from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime

from houba.errors import UsageOracleError
from houba.ports.usage_oracle import UsageObservation, UsageQuery


class CommandUsageAdapter:
    def __init__(self, command: str, timeout: int = 30) -> None:
        self._argv = shlex.split(command)
        if not self._argv:
            raise UsageOracleError("empty usage oracle command (HOUBA_USAGE_ORACLE_CMD)")
        self._timeout = timeout

    def last_prod_usage(self, query: UsageQuery) -> UsageObservation:
        payload = json.dumps(
            {
                "digest": query.digest,
                "image_ref": query.image_ref,
                "identity": {
                    "policy": query.identity.policy,
                    "import": query.identity.import_,
                    "variant": query.identity.variant,
                },
                "since": query.since.isoformat(),
            }
        )
        try:
            r = subprocess.run(  # noqa: S603
                self._argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                input=payload,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise UsageOracleError(str(e)) from e
        if r.returncode != 0:
            raise UsageOracleError(f"usage oracle failed: {r.stderr.strip()}")
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            raise UsageOracleError(f"invalid JSON from usage oracle: {e}") from e
        if not isinstance(data, dict):
            raise UsageOracleError(f"expected JSON object from usage oracle: {data!r}")
        return UsageObservation(
            last_seen=_parse_last_seen(data.get("last_seen")),
            detail=str(data.get("detail", "")),
        )


def _parse_last_seen(value: object) -> datetime | None:
    """`null`/absent => None (genuinely unseen => purgeable). A present-but-malformed
    timestamp raises (fail-closed): never let a bad value masquerade as 'unseen'."""
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise UsageOracleError(f"invalid last_seen from usage oracle: {value!r}")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise UsageOracleError(f"invalid last_seen timestamp {value!r}: {e}") from e
