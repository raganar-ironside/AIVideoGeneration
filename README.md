# HistoryForgeAI

A **modular, WSL2-first** Python pipeline for short-form Indian-history documentary videos.

> **Important:** This repository is a working prototype, not an unattended historical fact-checker or a complete AI text-to-video generator. The offline demo uses deterministic sample narration and locally generated documentary title-card visuals. Real historical imagery is optional via Wikimedia Commons. Gemini and Ollama can generate draft scripts/scene plans. Human review of claims, sources, licences, visuals and final videos is required before publication.

## What works today

| Stage | Implementation | Status |
| --- | --- | --- |
| Job creation / manifests | Filesystem JSON repository | Working |
| Research notes | Wikipedia discovery API | Optional; **not verification** |
| Script + scene plan | Mock, Gemini REST, Ollama REST | Working adapters; live services require access |
| Historical images | Wikimedia Commons API | Optional; may miss assets; licence review required |
| Image fallback | Pillow-generated title cards | Working |
| Narration | `espeak-ng` | Optional, basic robotic voice |
| Rendering | FFmpeg vertical MP4 | Working when FFmpeg installed |
| Testing | pytest | Working |
| Premium AI image/video | Not implemented | Future provider adapter |
| Auto-upload / scheduling | Not implemented | Future phase; manual approval required |

## WSL2 Ubuntu setup

Recommended project path: `~/projects/historyforgeai` (not `/mnt/c`, for performance).

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg espeak-ng git unzip fonts-dejavu-core
mkdir -p ~/projects/historyforgeai
cd ~/projects/historyforgeai
# Unzip the downloaded archive into this directory, or clone the repo.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
python -m pytest -q
```

**If downloading the ZIP to Windows Downloads:**

```bash
mkdir -p ~/projects
cd ~/projects
unzip /mnt/c/Users/z004hwfy/Downloads/historyforgeai_full.zip
cd historyforgeai
bash scripts/bootstrap.sh
```

**Do not unzip over an existing repository.** If migrating, back up the old directory first. Old Phase 1 manifest JSON is not automatically migrated to the new schema; retain it as an archive until a dedicated migration is written.

## Try it — no API key, no network

```bash
source .venv/bin/activate
historyforgeai run --topic "Ashoka and the Kalinga War" --provider mock
historyforgeai list
historyforgeai topics
```

The command prints a job ID. Its files are in `workspace/jobs/<job-id>/`:
- `manifest.json`: job status and paths
- `scene_plan.json`: script, scenes and unverified claims
- `research_notes.txt`: research context or explicit absence of sources
- `narration.wav`: audio if `espeak-ng` is installed
- `short.mp4`: vertical video if FFmpeg is installed

The **mock content is only a pipeline smoke test**, not an accurate historical documentary. Video frames are static cards; this first renderer does not animate images or generate cinematic footage.

### Generate a script without rendering

```bash
historyforgeai run --topic "The Chola navy" --provider mock --no-render
```

### Use Gemini

Set in `.env`:

```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Then run:

```bash
historyforgeai run --topic "Ashoka and the Kalinga War" --provider gemini --research --assets
```

Provider access, quotas, model availability, and costs vary. The pipeline does **not yet enforce** the budget settings in `configs/development.json`; avoid unattended paid runs until metering and spending guardrails are implemented.

### Use Ollama locally

Install Ollama separately in WSL or connect to a reachable Ollama server, then:

```bash
ollama pull llama3.2:3b
historyforgeai run --topic "The Chola navy" --provider ollama --no-render
```

Ollama's structured output depends on the chosen model's capabilities; smaller models may fail schema validation. Local LLM inference is separate from AI video generation and should run on modest hardware more easily.

## Architecture

```text
src/historyforgeai/
  cli.py                       # CLI entrypoint
  bootstrap.py                 # Dependency composition root
  config.py                    # Settings
  domain/models.py             # Validated entities and job states
  application/ports/           # Provider interfaces (Protocol)
  application/pipeline.py      # Workflow orchestration
  infrastructure/
    llm/                       # Mock / Gemini / Ollama
    research/                  # Wikipedia discovery
    assets/                    # Wikimedia Commons
    speech/                    # espeak-ng
    rendering/                 # FFmpeg + Pillow
    persistence/               # Filesystem job repository
configs/development.json       # Defaults (some future guardrails)
data/topics.csv                # Topic queue (listing only)
tests/                         # Unit tests
workspace/jobs/                # Generated job files, ignored by Git
```

Design principles: ports-and-adapters, dependency inversion, composition root, typed Pydantic schemas, no provider SDK imports in application logic, and per-job output folders. Providers can be swapped without rewriting the workflow. We have intentionally **not** added placeholder modules for unimplemented features.

## Limitations / next work

1. Verified research workflow with source provenance and human approval.
2. Asset ranking, rights filtering, image resizing/cropping review and attribution export.
3. Natural voice TTS and word-level subtitles.
4. Cinematic animation (pan/zoom) and optional GPU-based video generation.
5. Idempotent stage checkpoints, retry/backoff, monthly budget enforcement, and queue scheduling.
6. YouTube upload integration after review/approval.

**Editorial policy:** LLM-generated citations are not evidence. Verify claims using primary sources and reputable scholarship; don't portray artistic reconstructions as historical photographs. Wikimedia Commons licences differ and may require attribution or share-alike conditions.

## Development commands

```bash
python -m pytest -q
python -m compileall -q src
historyforgeai --help
```

If FFmpeg reports an encoder error, verify your installation with `ffmpeg -encoders | grep libx264`. For WSL video generation on Intel integrated graphics, use the CPU-based mock renderer first; heavy diffusion video models usually need a suitable GPU or cloud service.


## Visual timeline and character continuity (new)

See [docs/VISUAL_WORKFLOW.md](docs/VISUAL_WORKFLOW.md). Use `historyforgeai run --topic "Ashoka" --provider mock --scene-audio --motion zoom_in` to time scenes from synthesized speech. Add reusable canonical artwork using `historyforgeai characters add`, then `characters approve`. This does not automatically generate character portraits.
