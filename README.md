# HistoryForgeAI

**HistoryForgeAI** is a modular Python pipeline for creating Indian-history documentary YouTube Shorts. The GitHub repository is [AIVideoGeneration](https://github.com/raganar-ironside/AIVideoGeneration); the installed package and CLI are named `historyforgeai`.

> **Project status:** Working prototype, not a fully automated documentary producer. AI-generated scripts and historical claims require fact-checking. Review visuals, source licences, narration, and final videos before publication.

## Features

| Area | Implemented | Important limitations |
| --- | --- | --- |
| Script and scene planning | Mock, Gemini, Ollama, Groq, OpenRouter, OpenAI | API credentials/model availability vary; drafts are not verified history |
| Research | Optional Wikipedia background discovery | Not a fact-checking system |
| Manual script import | JSON import with scene narration and duration validation | User must supply valid scene data |
| Image sourcing | Wikimedia Commons, manual files, Hugging Face, OpenAI | Hosted calls may cost money; all candidate images require review |
| Storyboard review | Scene-by-scene approval, optional Streamlit UI | No automatic approval |
| Character references | Registry of canonical character images | Does not guarantee AI-generated character consistency |
| Narration | Optional `espeak-ng`; scene-by-scene timing option | Robotic voice; natural Hindi/English TTS not yet integrated |
| Video | FFmpeg vertical MP4, static/zoom-in/zoom-out motion | No generative AI video |
| Jobs and tests | Filesystem JSON manifests; pytest tests | Local workspace is not backed up by Git |

**Not yet implemented:** natural neural narration, word-level subtitles, automated historical verification, enforced API budget limits, automatic YouTube upload/scheduling, or reliable AI character identity preservation.

## Setup — Ubuntu on WSL2

Python 3.11+ is required. Prefer the WSL Linux filesystem rather than `/mnt/c`.

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg espeak-ng git fonts-dejavu-core

# Use your SSH alias if configured:
git clone git@github-personal:raganar-ironside/AIVideoGeneration.git
cd AIVideoGeneration
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,review,images]'
cp .env.example .env
python -m pytest -q
historyforgeai --help
```

Without a personal SSH alias, use `git clone https://github.com/raganar-ironside/AIVideoGeneration.git`. The `review` extra installs Streamlit and `images` installs the Hugging Face client. Never commit `.env` or API keys.

## Quick start

### Offline demo

```bash
historyforgeai run --topic "Ashoka and the Kalinga War" --provider mock
historyforgeai list
historyforgeai topics
```

The mock provider is for testing the pipeline, not for producing accurate historical content. Outputs are stored in `workspace/jobs/<JOB_ID>/`, including a manifest, scene plan, and optional narration and MP4.

### Generate a script without rendering

```bash
# Set GEMINI_API_KEY in .env first
historyforgeai run --topic "Rajendra Chola and the Chalukyas" --provider gemini --research --no-render
```

Other supported providers: `mock`, `ollama`, `groq`, `openrouter`, `openai`. Use `--model` to override supported models. OpenAI and potentially paid OpenRouter calls require `--allow-paid`; this is a consent flag, **not** a spending cap.

### Import a manually written narration

```bash
historyforgeai import-script --file my_script.json
```

The JSON must include `topic`, `title`, `duration_seconds`, `narration`, and `scenes`. Scene fields follow the `Scene` model in `src/historyforgeai/domain/models.py`. Scene durations must sum to the total, and scene narration must concatenate to the full narration. The command creates a planned job and prints its ID.

### Create, review, and render a storyboard

Use the job ID printed by `run --no-render` or `import-script`:

```bash
historyforgeai storyboard --job JOB_ID
historyforgeai image --job JOB_ID --scene 1 --provider manual --file ~/Pictures/scene1.png
streamlit run src/historyforgeai/interfaces/storyboard_app.py -- workspace/jobs/JOB_ID
```

In the Streamlit reviewer, inspect images, licences, and attribution and mark **every** scene `approved`. Then render:

```bash
historyforgeai render --job JOB_ID --motion zoom_in
```

The render command rejects incomplete or unapproved storyboards. It reuses `narration.wav` if present; **it does not synthesize narration** for imported jobs. Without that audio file, output may be silent. Adding a new image candidate resets the scene to `pending_review`.

### Generate hosted image candidates

```bash
# Set HF_TOKEN in .env
historyforgeai image --job JOB_ID --scene 1 --provider huggingface --allow-paid

# Or set OPENAI_API_KEY in .env
historyforgeai image --job JOB_ID --scene 1 --provider openai --allow-paid
```

You can specify `--model`. Hosted generation can incur charges; generated candidates still require manual approval.

### Scene-aligned audio and motion

```bash
historyforgeai run --topic "The Chola navy" --provider mock --scene-audio --motion zoom_in
```

This mode synthesizes speech separately for each scene, measures it with FFprobe, and adjusts scene durations. Available motion choices are `static`, `zoom_in`, and `zoom_out`. It currently uses eSpeak, not a natural documentary voice.

### Character references

```bash
historyforgeai characters add --id rajendra-chola --name "Rajendra Chola" --universe chola --description "Chola emperor"
historyforgeai characters approve --id rajendra-chola --image ~/Pictures/rajendra.png
historyforgeai characters list
```

The registry manages approved reference artwork; hosted image APIs do not automatically enforce matching faces or costumes.

## Configuration

Create `.env` from `.env.example`. Common variables:

| Service | Variables |
| --- | --- |
| Default script provider | `LLM_PROVIDER` |
| Gemini | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| Ollama | `OLLAMA_URL`, `OLLAMA_MODEL` |
| Groq | `GROQ_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| OpenAI scripts/images | `OPENAI_API_KEY` |
| Hugging Face images | `HF_TOKEN`, optional `HF_IMAGE_MODEL` |
| Wikimedia Commons | `WIKIMEDIA_USER_AGENT` |

Provider costs, rate limits, models, and availability can change. The project does not yet enforce the budget settings in `configs/development.json`.

## Architecture

```text
src/historyforgeai/
  cli.py                        CLI commands
  bootstrap.py                  Dependency wiring
  domain/                       Jobs, scenes, characters
  application/
    pipeline.py                 Workflow orchestration
    services/
      manual_script.py          JSON script import
      storyboard.py             Review and approval
      image_candidates.py       Manual/hosted images
      render_job.py             Approved-only rendering
      timeline.py               Scene timing
      visuals.py                Character reference resolution
  infrastructure/
    llm/                        Script providers
    research/                   Wikipedia discovery
    assets/                     Wikimedia Commons
    speech/                     eSpeak
    rendering/                  FFmpeg and motion
    persistence/                Job/character storage
  interfaces/storyboard_app.py  Streamlit reviewer
tests/                          Automated tests
workspace/                      Generated files (Git-ignored)
```

See [visual workflow documentation](docs/VISUAL_WORKFLOW.md) for more details.

## Development checks

```bash
python -m pytest -q
python -m compileall -q src
historyforgeai --help
ffmpeg -encoders | grep libx264
```

Tests are available but do not verify live paid API access or the historical accuracy of scripts.

## Roadmap

1. Natural, deep Indian documentary narration with Hindi/English support.
2. Better scene prompts and consistent characters across generated images.
3. Research citations, editorial fact-checking, and licence/attribution export.
4. Subtitles, improved video effects, and audio quality.
5. Job retries, cost metering, and monthly budget enforcement.
6. Optional YouTube publishing after explicit human approval.

**Editorial note:** Never portray AI reconstructions as historical photographs. Verify historical claims using reliable sources and comply with image licences, attribution, and share-alike obligations.
