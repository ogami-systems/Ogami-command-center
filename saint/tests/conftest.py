"""Shared fixtures and fake-response builders for the trust-boundary suite.

The builders here (make_response/tool_use_block/text_block) mirror the exact
SimpleNamespace-based fakes used for ad hoc verification earlier in this
project's build — formalized here rather than reinvented, per the "reuse
before duplicate" rule.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from db import Database


@pytest.fixture
def fake_config():
    return SimpleNamespace(
        anthropic_api_key="x",
        telegram_bot_token="123456:FAKE-TOKEN-FOR-TESTS",
        telegram_owner_id=999999,
        model_daily_budget_usd=5.00,
        max_escalations_per_run=2,
        saint_timezone="UTC",
        saint_log_level="INFO",
    )


@pytest.fixture
def database(tmp_path):
    return Database(tmp_path / "test.db")


@pytest.fixture
def fake_anthropic_client():
    """`.messages.create` is a MagicMock — set `.side_effect = [...]` in a test
    to script a sequence of responses across successive calls."""
    client = SimpleNamespace()
    client.messages = SimpleNamespace()
    client.messages.create = MagicMock()
    return client


class FakeUsage:
    input_tokens = 100
    output_tokens = 50


def make_response(stop_reason: str, content: list):
    return SimpleNamespace(stop_reason=stop_reason, content=content, usage=FakeUsage())


def tool_use_block(name: str, input_: dict, id_: str = "tu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=id_)


def text_block(text: str):
    return SimpleNamespace(type="text", text=text)
