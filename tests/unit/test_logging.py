import json
import logging
from io import StringIO

import structlog

from hub2hub.logging import configure


def test_text_format_produces_human_readable() -> None:
    buf = StringIO()
    configure(format_="text", level="INFO", stream=buf)

    log = structlog.get_logger("test")
    log.info("hello", project="p1", tag="v1")

    out = buf.getvalue()
    assert "hello" in out
    assert "project=p1" in out
    assert "tag=v1" in out


def test_json_format_produces_one_object_per_line() -> None:
    buf = StringIO()
    configure(format_="json", level="INFO", stream=buf)

    log = structlog.get_logger("test")
    log.info("hello", project="p1", tag="v1")

    line = buf.getvalue().strip()
    obj = json.loads(line)
    assert obj["event"] == "hello"
    assert obj["project"] == "p1"
    assert obj["tag"] == "v1"
    assert obj["level"] == "info"


def test_level_filters_debug() -> None:
    buf = StringIO()
    configure(format_="text", level="INFO", stream=buf)

    log = structlog.get_logger("test")
    log.debug("noisy")

    assert buf.getvalue() == ""


def test_warn_alias_for_warning() -> None:
    buf = StringIO()
    configure(format_="json", level="WARN", stream=buf)

    log = structlog.get_logger("test")
    log.info("filtered")
    log.warning("kept")

    lines = [line for line in buf.getvalue().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "kept"


def teardown_module() -> None:  # restore root logger config
    logging.getLogger().handlers.clear()
