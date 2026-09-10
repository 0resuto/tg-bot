from __future__ import annotations

from bot.domain.models import MemoryFact
from bot.prompts.extraction import build_extraction_prompt
from bot.prompts.persona import build_persona_prompt


def test_build_persona_prompt():
    quick_facts = {"Alice": [MemoryFact(fact_text="likes flat white", subject_name="Alice")]}
    deep_facts = [MemoryFact(fact_text="visited Rome last year")]

    prompt = build_persona_prompt(
        base_prompt="Custom persona",
        quick_facts=quick_facts,
        deep_facts=deep_facts,
        bot_language="ru",
    )

    assert "Custom persona" in prompt
    assert "Alice" in prompt
    assert "likes flat white" in prompt
    assert "visited Rome last year" in prompt


def test_build_extraction_prompt():
    prompt = build_extraction_prompt(sensitive_categories=["health", "finance"])
    assert "health" in prompt.lower()
    assert "finance" in prompt.lower()
    assert "extract" in prompt.lower()
