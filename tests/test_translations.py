"""strings.json and every translation stay in sync with each other and the code."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.klipsch_flexus.const import (
    API_PATHS,
    EQ_PRESET_CUSTOM,
    EQ_PRESETS,
    IDLE_TIMEOUTS,
    SOURCES,
)

COMPONENT = Path(__file__).parent.parent / "custom_components" / "klipsch_flexus"
STRINGS = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
TRANSLATIONS = sorted((COMPONENT / "translations").glob("*.json"))


def _keys(node: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        out |= _keys(value, path) if isinstance(value, dict) else {path}
    return out


@pytest.mark.parametrize("path", TRANSLATIONS, ids=lambda p: p.name)
def test_translation_keys_match_strings(path: Path) -> None:
    assert _keys(json.loads(path.read_text(encoding="utf-8"))) == _keys(STRINGS)


def test_state_translations_cover_the_code() -> None:
    entity = STRINGS["entity"]
    assert set(entity["select"]["eq_preset"]["state"]) == {*EQ_PRESETS, EQ_PRESET_CUSTOM}
    assert set(entity["select"]["idle_timeout"]["state"]) == set(IDLE_TIMEOUTS)
    assert set(entity["sensor"]["active_input"]["state"]) == set(SOURCES)
    assert "idle_timeout" not in entity["number"]  # it is a select now


def test_subwoofer_level_names() -> None:
    """sub_wired is the wired RCA output; sub_wireless is all wireless subs together."""
    english = json.loads((COMPONENT / "translations" / "en.json").read_text(encoding="utf-8"))
    for source in (STRINGS, english):
        number = source["entity"]["number"]
        assert number["sub_wired"]["name"] == "Channel: Wired Subwoofer"
        assert number["sub_wireless"]["name"] == "Channel: Wireless Subwoofers"


def test_subwoofer_keys_map_to_firmware_nodes() -> None:
    """The 'Wired' label must drive the wired node, not the wireless one."""
    assert API_PATHS["sub_wired"] == "settings:/cinema/dsp/wiredSubwooferVolume"
    assert API_PATHS["sub_wireless"] == "settings:/cinema/dsp/wirelessSubwoofersVolume"


def test_reconfigure_abort_strings_exist() -> None:
    assert {"reconfigure_successful", "already_in_progress"} <= set(STRINGS["config"]["abort"])
