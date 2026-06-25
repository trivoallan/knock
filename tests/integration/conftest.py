import socket
import subprocess
import time

import pytest

redis = pytest.importorskip("redis")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def redis_server():
    """A real redis-server. Uses REDIS_TEST_ADDR if set, else spawns redis-server from
    PATH, else skips. Tests get a decode_responses=True client."""
    import os

    if os.environ.get("REDIS_TEST_ADDR"):
        host, port = os.environ["REDIS_TEST_ADDR"].split(":")
        client = redis.Redis(host=host, port=int(port), decode_responses=True)
        client.flushall()
        yield client
        return
    import shutil

    if not shutil.which("redis-server"):
        pytest.skip("redis-server not on PATH and REDIS_TEST_ADDR unset")
    port = _free_port()
    proc = subprocess.Popen(
        ["redis-server", "--port", str(port), "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = redis.Redis(host="127.0.0.1", port=port, decode_responses=True)
    for _ in range(50):
        try:
            client.ping()
            break
        except redis.exceptions.ConnectionError:
            time.sleep(0.1)
    try:
        yield client
    finally:
        proc.terminate()
        proc.wait(timeout=5)
