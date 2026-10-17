# LLM provider selection

HistoryForgeAI supports manual import without an API, plus the following script-generation providers:

| Provider | Example | Billing notes |
| --- | --- | --- |
| mock | `--provider mock` | Offline, no charge |
| ollama | `--provider ollama` | Local, no API charge |
| gemini | `--provider gemini` | Free tiers and paid tiers depend on account/model |
| groq | `--provider groq` | Rate-limited free tier; check account |
| openrouter | `--provider openrouter --model openrouter/free` | Free routing; availability varies |
| openai | `--provider openai --allow-paid` | API billed separately from ChatGPT Plus |

Store keys in `.env` (gitignored):

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=replace_me
GROQ_API_KEY=replace_me
OPENROUTER_API_KEY=replace_me
OPENAI_API_KEY=replace_me
# Optional: GROQ_MODEL=..., OPENROUTER_MODEL=..., OPENAI_MODEL=...
```

Use the default from `LLM_PROVIDER`:

```bash
historyforgeai run --topic "Rajendra Chola" --no-render --no-audio
```

Override per job:

```bash
historyforgeai run --topic "Rajendra Chola" --provider groq --no-render --no-audio
historyforgeai run --topic "Rajendra Chola" --provider openrouter --model openrouter/free --no-render --no-audio
historyforgeai run --topic "Rajendra Chola" --provider openai --allow-paid --no-render --no-audio
```

OpenAI and non-`:free` OpenRouter model selections require `--allow-paid`. **This is a guardrail, not a spending cap**. Gemini/Groq account tiers may also be billable; confirm billing settings in each provider dashboard. No automatic paid fallback is implemented. Model selection via `--model` currently applies to Groq, OpenRouter and OpenAI; Gemini uses `GEMINI_MODEL`, Ollama uses `OLLAMA_MODEL`.

Manual scripts are unchanged:

```bash
historyforgeai import-script --file examples/manual_script.json
```

This PR only switches the script/scene-plan LLM. Image and voice provider switching will be implemented separately.
