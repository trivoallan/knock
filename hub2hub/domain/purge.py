"""Sélection des tags d'archive à purger.

Référence : vars/importProduct.groovy:1348-1435 (purgeArchives).
Convention : <base>_YYYYMMDD.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta

_ARCHIVE_RE = re.compile(r"^(?P<base>.+)_(?P<date>\d{8})$")


def _parse(tag: str) -> tuple[str, datetime] | None:
    m = _ARCHIVE_RE.match(tag)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group("date"), "%Y%m%d")
    except ValueError:
        return None
    return m.group("base"), dt


def compute_archives_to_purge(
    archives: list[str],
    *,
    keep: int,
    older_than_days: int,
    now: datetime,
) -> list[str]:
    by_base: dict[str, list[tuple[str, datetime]]] = defaultdict(list)
    for tag in archives:
        parsed = _parse(tag)
        if parsed is None:
            continue
        base, dt = parsed
        by_base[base].append((tag, dt))

    threshold = now.replace(tzinfo=None) - timedelta(days=older_than_days)
    purged: list[str] = []
    for entries in by_base.values():
        entries.sort(key=lambda e: e[1], reverse=True)
        for tag, dt in entries[keep:]:
            if dt < threshold:
                purged.append(tag)
    return purged
