"""Configuration de structlog pour le CLI h2h.

Voir spec §6.3 — logs structurés JSON/text.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal, TextIO

import structlog


def _level_to_int(level: str) -> int:
    normalized = "WARNING" if level == "WARN" else level
    return getattr(logging, normalized)  # type: ignore[no-any-return]


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

    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(_level_to_int(level))

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if format_ == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_level_to_int(level)),
        logger_factory=structlog.PrintLoggerFactory(stream),
        cache_logger_on_first_use=False,
    )
