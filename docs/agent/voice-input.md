# Voice input — реализация

**Status:** implemented (feature flag `VOICE_ENABLED`)  
**Branch:** `feature/voice-input`  
**Reference:** `../AudioToText` — паттерны Whisper перенесены

## Pipeline

```
Voice → Whisper → transcript → [regex fast path | LLM JSON] → CommandExecutor → TransactionService
```

## Modules

| Path | Role |
|------|------|
| `telegram_bot/voice/transcription.py` | Whisper API, OGG→MP3, chunking, retry |
| `telegram_bot/voice/audio_download.py` | Download from Telegram |
| `telegram_bot/voice/openai_client.py` | OpenAI client + SOCKS/HTTP proxy |
| `telegram_bot/voice/config.py` | Env flags |
| `telegram_bot/voice/intents.py` | Intent enum + ParsedVoiceCommand |
| `telegram_bot/voice/interpreter.py` | Regex + LLM structured extract |
| `telegram_bot/voice/router.py` | Intent → handler + stubs |
| `telegram_bot/services/command_executor.py` | Shared tx creation (text + voice) |
| `telegram_bot/handlers/voice_handler.py` | Entry point |
| `telegram_bot/prompts/voice_command.txt` | LLM system prompt |

## Intents

| Intent | Status |
|--------|--------|
| `CREATE_TRANSACTION` | implemented |
| `SET_BUDGET` | stub |
| `MANAGE_GOAL` | stub |
| `ASK_ADVISOR` | stub + log |

## UX

- Auto-save: confidence ≥ 0.85 + category resolved
- Confirm: 0.5–0.85 or ambiguous category (`voice_confirm_yes` / `voice_cancel`)
- Reject: < 0.5
- ActionKeyboard + `🎤 Распознано: «…»` after save
- Interactive states: voice → transcript as text (`_voice_text_override`)

## Env

`VOICE_ENABLED`, `OPENAI_API_KEY`, `OPENAI_PROXY_URL`, `TRANSCRIPTION_MODEL`, `VOICE_LLM_MODEL`, `WHISPER_PROMPT`, `WHISPER_LANGUAGE`

`OPENAI_PROXY_URL` — если не задан, используется `TELEGRAM_PROXY_URL`. Для Whisper/LLM нужен proxy с **выходом в стране, где OpenAI доступен** (EU/US); московский SOCKS для Telegram может не подойти.

## Implementation checklist

- [x] deps-docker: pyproject, Dockerfile ffmpeg, env
- [x] transcription-layer
- [x] command-executor refactor
- [x] llm-interpreter + router
- [x] voice-handler + run_bot registration
- [x] ux-confirm flow
- [x] future intent stubs
- [x] tests (ParsedVoiceCommand, regex fast path)

## Tests

```bash
python manage.py test telegram_bot.tests.ParsedVoiceCommandTests telegram_bot.tests.VoiceInterpreterRegexTests
```

## Phase 2 (backlog)

- Whisper prompt tuning per user categories
- Metrics: transcribe/parse latency
- Local Whisper option (privacy)
