from __future__ import annotations

from knock.domain.coverage import is_stamped


def test_stamped_via_prefixed_policy_key() -> None:
    assert is_stamped({"io.knock.policy": "redis"}, prefix="io.knock") is True


def test_unstamped_when_no_knock_keys() -> None:
    assert (
        is_stamped({"org.opencontainers.image.source": "docker.io/x"}, prefix="io.knock") is False
    )
    assert is_stamped({}, prefix="io.knock") is False


def test_base_digest_alone_is_not_stamped_under_nonempty_prefix() -> None:
    # The strong signal is the prefixed key; base.digest alone (an OCI-standard key another
    # tool could set) is NOT treated as a knock stamp when a prefix is configured.
    assert (
        is_stamped({"org.opencontainers.image.base.digest": "sha256:x"}, prefix="io.knock") is False
    )


def test_empty_prefix_falls_back_to_base_digest() -> None:
    assert is_stamped({"org.opencontainers.image.base.digest": "sha256:x"}, prefix="") is True
    assert is_stamped({}, prefix="") is False


def test_custom_prefix() -> None:
    assert is_stamped({"com.acme.policy": "redis"}, prefix="com.acme") is True
    assert is_stamped({"io.knock.policy": "redis"}, prefix="com.acme") is False
