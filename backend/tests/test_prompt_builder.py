"""Property-based and unit tests for prompt_builder."""
from __future__ import annotations
import pytest
from hypothesis import given, assume
from hypothesis import strategies as st

from backend.app.tone_detector import Tone
from backend.app.prompt_builder import (
    BASE_ADVISOR_RULES,
    build_tone_aware_system_prompt,
    get_tone_instruction_block,
)


# ── Property tests ────────────────────────────────────────────────────

@given(tone=st.sampled_from(Tone))
def test_prompt_always_nonempty_with_base_rules(tone):
    """Property 5: non-empty string containing base rules for any tone."""
    result = build_tone_aware_system_prompt(tone)
    assert result
    assert "Only recommend perfumes from the provided dataset" in result


@given(
    t1=st.sampled_from(Tone),
    t2=st.sampled_from(Tone),
)
def test_distinct_tones_distinct_blocks(t1, t2):
    """Property 6: each tone produces a distinct instruction block."""
    assume(t1 != t2)
    block1 = get_tone_instruction_block(t1)
    block2 = get_tone_instruction_block(t2)
    assert block1 != block2


@given(
    tone=st.sampled_from(Tone),
    name=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Ll", "Lu"))),
)
def test_name_hint_present_iff_name_provided(tone, name):
    """Property 7: name hint present iff name is provided."""
    stripped = name.strip()
    assume(stripped)

    # Use a simple namespace object to avoid Python class-body scoping issues
    ctx = type("FakeCtx", (), {"nickname": stripped, "name": ""})()

    with_name = build_tone_aware_system_prompt(tone, user_ctx=ctx)
    without_name = build_tone_aware_system_prompt(tone, user_ctx=None)

    assert stripped in with_name
    assert "Use it naturally once" in with_name
    assert "Use it naturally once" not in without_name


# ── Unit tests ────────────────────────────────────────────────────────

def test_each_tone_returns_nonempty():
    for tone in Tone:
        result = build_tone_aware_system_prompt(tone)
        assert result, f"Empty prompt for tone {tone}"


def test_base_rules_always_present():
    for tone in Tone:
        result = build_tone_aware_system_prompt(tone)
        assert "Only recommend perfumes from the provided dataset" in result


def test_get_tone_instruction_block_distinct():
    blocks = [get_tone_instruction_block(t) for t in Tone]
    assert len(set(blocks)) == len(blocks), "Tone blocks are not all distinct"


def test_name_hint_with_nickname():
    class Ctx:
        nickname = "Anuj"
        name = ""
    result = build_tone_aware_system_prompt(Tone.FRIENDLY, user_ctx=Ctx())
    assert "Anuj" in result
    assert "Use it naturally once" in result


def test_name_hint_absent_without_ctx():
    result = build_tone_aware_system_prompt(Tone.FRIENDLY, user_ctx=None)
    assert "Use it naturally once" not in result


def test_name_hint_with_name_field():
    class Ctx:
        nickname = ""
        name = "Priya"
    result = build_tone_aware_system_prompt(Tone.PROFESSIONAL, user_ctx=Ctx())
    assert "Priya" in result
