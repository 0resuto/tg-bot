# Prompts & AI Persona Configuration

This directory contains persona templates and heuristic noise filter configurations for the Telegram Memory Bot.

## Files

- **`noise_filter.json`**: Heuristic noise filtering rules (minimum message length, command prefixes, standalone media tags, stopwords, and regex patterns) used to discard conversational filler before ingestion into Graphiti.
- **`system_prompt.example.md`**: Template reference for authoring the bot's system persona prompt.
- **`system_prompt.md`** *(gitignored)*: Real deployment persona prompt. Copy from `system_prompt.example.md` and customize for your bot:
  ```bash
  cp prompts/system_prompt.example.md prompts/system_prompt.md
  ```

## Security & Git Discipline

Real AI personas and proprietary system instructions in `system_prompt.md` are deliberately excluded from Git via `.gitignore` to prevent leaking production personas or private instructions into public repositories.
