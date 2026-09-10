"""
Extraction prompt builder.
"""

from __future__ import annotations


def build_extraction_prompt(sensitive_categories: list[str]) -> str:
    skip_cats = ", ".join(sensitive_categories) if sensitive_categories else "none"

    prompt = (
        "Extract factual statements from the user's message. Focus on extracting the following information:\n"
        "- Personal preferences\n"
        "- Hobbies\n"
        "- Life events\n"
        "- Travel\n"
        "- Relationships\n"
        "- Recurring topics\n"
        "- Food and drink preferences\n"
        "- Work and study details\n"
        "- Pets\n"
        "- Habits\n\n"
        f"CRITICAL: Do NOT extract information related to the following sensitive categories: {skip_cats}.\n"
        "This includes health details, financial specifics, credentials, legal issues, explicit content, and political opinions.\n\n"
        "Format the extracted information as clear, concise factual statements."
    )

    return prompt
