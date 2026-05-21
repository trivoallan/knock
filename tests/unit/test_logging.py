import json
import logging
from collections.abc import Iterator
from io import StringIO

import pytest
import structlog

from hub2hub.logging import configure


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    yield
    logging.getLogger().handlers.clear()
    structlog.reset_defaults()


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


def test_stdlib_loggers_routed_through_json_renderer() -> None:
    """Spec §6.3 : tout log (y compris stdlib / dépendances tierces) doit être du JSON."""
    buf = StringIO()
    configure(format_="json", level="INFO", stream=buf)

    logging.getLogger("third_party.lib").warning("upstream retry %s", "502")

    line = buf.getvalue().strip()
    obj = json.loads(line)
    assert obj["event"] == "upstream retry 502"
    assert obj["level"] == "warning"


def test_exception_rendered_with_class_and_traceback_in_json() -> None:
    """Spec §6.3 : les exceptions doivent exposer error class / traceback."""
    buf = StringIO()
    configure(format_="json", level="INFO", stream=buf)

    log = structlog.get_logger("test")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        log.error("oops", exc_info=True)

    line = buf.getvalue().strip()
    obj = json.loads(line)
    assert obj["event"] == "oops"
    # structlog.processors.dict_tracebacks puts traceback under "exception"
    assert "exception" in obj
    # Verify class name is somewhere in the exception data
    blob = json.dumps(obj["exception"])
    assert "RuntimeError" in blob
    assert "boom" in blob


def test_autouse_reset_clears_config_between_tests() -> None:
    """Sanity check : la fixture autouse reset bien la config entre tests."""
    configure(format_="json", level="DEBUG", stream=StringIO())
    assert structlog.is_configured()
    structlog.reset_defaults()
    assert not structlog.is_configured()
