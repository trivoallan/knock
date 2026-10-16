from __future__ import annotations

from knock.domain.platforms import missing, normalize, same_set


def test_normalize_folds_arm64_v8() -> None:
    assert normalize("linux/arm64/v8") == "linux/arm64"
    assert normalize("Linux/AMD64") == "linux/amd64"
    assert normalize("linux/arm/v7") == "linux/arm/v7"


def test_missing_names_absent_platforms_in_request_order() -> None:
    assert missing(["linux/amd64"], ["linux/arm64", "linux/amd64", "linux/s390x"]) == [
        "linux/arm64",
        "linux/s390x",
    ]


def test_arm64_spellings_are_one_platform() -> None:
    assert missing(["linux/arm64/v8"], ["linux/arm64"]) == []
    assert missing(["linux/arm64"], ["linux/arm64/v8"]) == []


def test_variantless_request_takes_any_variant() -> None:
    assert missing(["linux/arm/v7"], ["linux/arm"]) == []
    assert missing(["linux/arm/v6"], ["linux/arm/v7"]) == ["linux/arm/v7"]


def test_same_set_ignores_order_and_spelling() -> None:
    assert same_set(["linux/arm64/v8", "linux/amd64"], ["linux/amd64", "linux/arm64"])
    assert not same_set(["linux/amd64"], ["linux/amd64", "linux/arm64"])
