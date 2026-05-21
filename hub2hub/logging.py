"""Configuration de structlog pour le CLI h2h.

Voir spec §6.3 — logs structurés JSON/text.

Les enregistrements stdlib (httpx, urllib3, etc.) sont routés via
`structlog.stdlib.ProcessorFormatter` afin que chaque ligne — qu'elle vienne
de structlog ou d'une dépendance tierce — passe par la même chaîne de
processeurs et le même renderer. Garantit l'invariant Splunk/Loki : 1 ligne
== 1 événement structuré, sans regex.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal, TextIO

import structlog


def _level_to_int(level: str) -> int:
    """Convertit un niveau (DEBUG/INFO/WARN/WARNING/ERROR) en entier stdlib."""
    return logging.getLevelName(level)  # type: ignore[no-any-return]


def configure(
    *,
    format_: Literal["text", "json"] = "text",
    level: str = "INFO",
    stream: TextIO | None = None,
) -> None:
    """(Re)configure structlog et logging stdlib.

    `stream` permet de rediriger vers un buffer dans les tests.
    """
    stream = stream if stream is not None else sys.stderr
    level_int = _level_to_int(level)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.types.Processor
    if format_ == "json":
        shared_processors.append(structlog.processors.dict_tracebacks)
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level_int)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )
