"""Assert that each example doc page embeds its source YAML verbatim."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "examples"

MAPPING: dict[str, list[str]] = {
    "reference.md": [
        "reference/busybox/busybox.yml",
        "reference/debian-tz/debian-tz.yml",
    ],
    "redis.md": ["redis/redis.yml"],
    "hardened.md": ["hardened/redis.yml"],
    "attested.md": ["attested/redis.yml"],
    "pending-deletion.md": ["pending-deletion/pending-deletion.yml"],
    "retention.md": ["retention/redis.yml"],
    "admission.md": ["admission/require-fresh-houba-scan.yaml"],
}


def _yaml_blocks(md: str) -> list[str]:
    return [b.strip() for b in re.findall(r"```yaml[^\n]*\n(.*?)```", md, re.S)]


def test_embedded_yaml_matches_source() -> None:
    for page, sources in MAPPING.items():
        blocks = _yaml_blocks((DOCS / page).read_text())
        assert len(blocks) == len(sources), (
            f"{page}: {len(blocks)} yaml block(s) found, expected {len(sources)}"
        )
        for block, src in zip(blocks, sources):
            source_text = (DOCS / src).read_text().strip()
            assert block == source_text, (
                f"{page} embedded yaml drifted from {src}"
            )
