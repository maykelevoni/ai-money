# Task 006: LLM + Telegram clients

## Description
Wrappers for content generation (Anthropic, cheap model) and notifications (Telegram Bot API). (Plan Section 5.)

## Files
- `src/clients/llm.py` (create)
- `src/clients/telegram.py` (create)

## Requirements
1. `llm.py`: wraps the Anthropic SDK pinned to a cheap model (Claude Haiku). `complete(system, prompt, max_tokens)` returning text. Centralize the model id so cost stays controlled. Use prompt caching where the system prompt is reused.
2. `telegram.py`: `send(text)` via Bot API `sendMessage` using TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID. Markdown enabled, fails soft (log, don't crash the engine) if Telegram is down.
3. Keys from `config.settings`.

## Existing Code to Reference
- `src/config.py` (Task 002).
- Anthropic SDK usage — see the `claude-api` skill conventions (caching, model ids).

## Acceptance Criteria
- [ ] `llm.complete(...)` returns text from the cheap model.
- [ ] `telegram.send(...)` delivers a message to the configured chat.
- [ ] Telegram failure logs a warning and does not raise.

## Dependencies
- Task 002

## Commit Message
feat: Anthropic LLM and Telegram notification clients
