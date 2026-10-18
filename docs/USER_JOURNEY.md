# Your first HistoryForgeAI Short

This guide follows the path a new user takes: **install → choose a script provider → configure narration → generate → review → find the video**.

HistoryForgeAI is a working prototype for Indian-history documentary Shorts, not a one-click publishing service. **Review historical claims, images, attribution, and audio before sharing.**

## 1. Install (Ubuntu / WSL2)

You need Python 3.11+, Git, FFmpeg, and eSpeak NG. In an Ubuntu terminal:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ffmpeg espeak-ng
git clone https://github.com/raganar-ironside/AIVideoGeneration.git
cd AIVideoGeneration
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,kokoro,edge,review]'
cp .env.example .env
python -m pytest -q
```

Run commands from the repository directory with the virtual environment activated.

## 2. Choose how scripts are written

Edit `.env`:

- **Try it without an API key:** `LLM_PROVIDER=mock`. This generates demonstration text, **not researched historical narration**.
- **Use Gemini:** `LLM_PROVIDER=gemini` and set `GEMINI_API_KEY`. Internet access is required.
- **Use local Ollama:** `LLM_PROVIDER=ollama`; start Ollama separately and configure `OLLAMA_URL` / `OLLAMA_MODEL`.

The CLI also supports Groq, OpenRouter, and OpenAI. Some hosted models may charge money. See the README for the `--allow-paid` flag. The app does not enforce a spending cap.

## 3. Choose your narration voice

For a simple offline test, eSpeak NG is already installed. To use the more natural **Kokoro Hindi voice**, download these files from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases) and place them in `models/`:

```text
models/
  kokoro-v1.0.onnx
  voices-v1.0.bin
```

The model files are downloaded separately and are not stored in Git.

Set these values in `.env`:

```dotenv
SPEECH_PROVIDER=auto
SPEECH_FALLBACK_ORDER=kokoro,edge,espeak
KOKORO_MODEL=models/kokoro-v1.0.onnx
KOKORO_VOICES=models/voices-v1.0.bin
KOKORO_VOICE=hm_psi
KOKORO_LANG=hi

VOICE_PRESET=epic
# Optional: override any preset value
# VOICE_SPEED=0.95
# VOICE_PITCH_SEMITONES=-2.0
# VOICE_BASS_DB=3
# VOICE_SENTENCE_PAUSE=0.35
```

Available presets: `normal`, `documentary`, `epic`. The `VOICE_*` overrides take precedence over preset defaults. Kokoro runs locally; Edge TTS is an online fallback; eSpeak NG is the final fallback. For Hindi, check the actual audio because voice/model bundles and pronunciation vary. See [narration configuration](SPEECH_PROVIDERS.md).

## 4. Make a first test video

```bash
historyforgeai run --topic "Rajendra Chola and the Chalukyas" --provider mock --scene-audio --motion zoom_in
```

This exercises the pipeline using **mock script content**. It is not ready to publish as historical fact. With `--scene-audio`, the app generates narration scene by scene and adjusts scene lengths using measured speech durations.

To draft with Gemini instead:

```bash
historyforgeai run --topic "Rajendra Chola and the Chalukyas" --provider gemini --research --scene-audio --motion zoom_in
```

`--research` retrieves Wikipedia background, **not verified citations or fact-checking**. Check the script yourself.

If you want the app to try downloading Wikimedia Commons images, add `--assets` after setting a real contact address in `WIKIMEDIA_USER_AGENT`. Without image assets, rendered scenes may use placeholders or other configured imagery. Review licences before publication.

## 5. Find your video

Each run prints a job record with its ID. You can also list jobs:

```bash
historyforgeai list
```

Files are stored under `workspace/jobs/JOB_ID/`. Look for:

- `scene_plan.json` — script and scene breakdown
- `research_notes.txt` — background text, when requested
- `narration.wav` — narration audio, if synthesized
- `timeline.json` — video/scene timing, when rendered
- The MP4 at the `video_path` printed in the job record

The `workspace/` directory is ignored by Git. Back up any videos you want to keep.

## 6. Optional: review images before rendering

If you prefer to approve the storyboard manually:

```bash
historyforgeai run --topic "Rajendra Chola" --provider gemini --no-render
historyforgeai storyboard --job JOB_ID
historyforgeai image --job JOB_ID --scene 1 --provider manual --file /absolute/path/to/scene1.png
streamlit run src/historyforgeai/interfaces/storyboard_app.py -- workspace/jobs/JOB_ID
```

Replace `JOB_ID` with the printed ID. Add/review images for all scenes, approve every scene in Streamlit, then run:

```bash
historyforgeai render --job JOB_ID --generate-audio --scene-audio --motion zoom_in
```

**Important:** `--no-render` skips narration generation. The later `render --generate-audio` synthesizes narration **after** all images are approved. Use `--scene-audio` for speech-measured scene timing. Without either option, `render` reuses existing `narration.wav` if present, otherwise the video may be silent.

## 7. Common problems

| Problem | What to check |
| --- | --- |
| `historyforgeai: command not found` | Activate `.venv` and run `python -m pip install -e .` |
| Kokoro falls back to Edge/eSpeak | Check both files in `models/`, the `KOKORO_*` paths, and installed `kokoro` extras |
| Voice preset seems ignored | Confirm `VOICE_PRESET` and `VOICE_*` in `.env`, then generate a **new** audio file |
| No speech in an approved storyboard render | `--no-render` did not create `narration.wav`; supply matching audio |
| No historical-looking visuals | Add `--assets` or supply and approve images; inspect the scene plan |
| Video rendering fails | Check `ffmpeg -version` and `ffprobe -version` |
| Script sounds inaccurate | Mock output is only a demo; even AI-generated history needs editorial verification |

## What the project does not do yet

No word-level subtitles, automatic historical fact-checking, automatic YouTube upload, or guaranteed consistent AI characters. Scene-audio timing is **scene-level**, not word-level.

For advanced commands and architecture, see the [README](../README.md) and [visual workflow](VISUAL_WORKFLOW.md).
