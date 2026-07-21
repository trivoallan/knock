"""structlog configuration for the knock CLI.

See spec §6.3 — structured JSON/text logs.

stdlib log records (httpx, urllib3, etc.) are routed through
`structlog.stdlib.ProcessorFormatter` so that every line — whether it comes
from structlog or from a third-party dependency — passes through the same
processor chain and the same renderer. This enforces the Splunk/Loki
invariant: 1 line == 1 structured event, no regex required.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal, TextIO

import structlog


def _level_to_int(level: str) -> int:
    """Convert a level name (DEBUG/INFO/WARN/WARNING/ERROR) to a stdlib integer."""
    return logging.getLevelName(level)  # type: ignore[no-any-return]


def configure(
    *,
    format_: Literal["text", "json"] = "text",
    level: str = "INFO",
    stream: TextIO | None = None,
) -> None:
    """(Re)configure structlog and the stdlib logging layer.

    `stream` can be used to redirect output to a buffer in tests.
    """
    stream = stream if stream is not None else sys.stderr
    level_int = _level_to_int(level)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer: structlog.types.Processor
    if format_ == "json":
        shared_processors.append(structlog.processors.dict_tracebacks)
        renderer = structlog.processors.JSONRenderer()
    else:
        shared_processors.append(structlog.processors.format_exc_info)
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
