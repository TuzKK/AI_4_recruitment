import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "source" / "boss-cli-main"))
from boss_cli.browser_bridge import BridgeState


def test_greeting_requires_write_enabled_bridge():
    bridge = BridgeState("test-token", allow_writes=False)
    with pytest.raises(ValueError, match="未启用"):
        bridge.call("greet", "1:document", {"geek_id": "c1"})


def test_write_enabled_bridge_recognizes_greeting_operation():
    bridge = BridgeState("test-token", allow_writes=True)
    with pytest.raises(ValueError, match="尚未连接"):
        bridge.call("greet", "1:document", {"geek_id": "c1"})
