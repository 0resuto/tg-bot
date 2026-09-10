"""
Persona prompt builder.
"""

from __future__ import annotations

from typing import Any


def build_persona_prompt(
    base_prompt: str,
    quick_facts: dict[str, list[Any]],
    deep_facts: list[Any],
    bot_language: str = "ru",
) -> str:
    default_preamble = (
        "Ты — дружелюбный и полезный ИИ-ассистент в групповом чате. "
        "Твоя задача — поддерживать беседу, отвечать на вопросы и быть интересным собеседником. "
        "Используй информацию о пользователях, чтобы делать ответы более персонализированными."
    )

    preamble = base_prompt.strip() if base_prompt else default_preamble

    lines = [preamble, "", "What you remember about the participants:"]

    if quick_facts:
        for user, facts in quick_facts.items():
            lines.append(f"\n- {user}:")
            for fact in facts:
                fact_desc = getattr(fact, "description", str(fact))
                lines.append(f"  * {fact_desc}")

    if deep_facts:
        lines.append("\nDeep search context:")
        for fact in deep_facts:
            fact_desc = getattr(fact, "description", str(fact))
            lines.append(f"- {fact_desc}")

    lines.extend(["", f"Please reply in the following language: {bot_language}."])

    return "\n".join(lines)
