# Scene image candidates (manual and hosted)

First create a job with `historyforgeai import-script --file ...` or `historyforgeai run --provider gemini --no-render --no-audio`, then create its storyboard:

```bash
historyforgeai storyboard --job JOB_ID
```

## Manual images — no API cost

Generate an image using a permitted free trial, download it, then import:

```bash
historyforgeai image --job JOB_ID --scene 1 --provider manual --file ~/Downloads/scene1.png
```

Repeat for each scene. Images are copied into `workspace/jobs/JOB_ID/assets/` and converted to JPEG. They remain `pending_review` even if a prior image was approved. Check each generator's commercial use, attribution, and free-trial terms.

## Hosted generation

Set `HF_TOKEN` or `OPENAI_API_KEY` in the gitignored `.env`. Install optional dependencies:

```bash
python -m pip install -e '.[images,review,dev]'
```

```bash
historyforgeai image --job JOB_ID --scene 1 --provider huggingface --allow-paid
historyforgeai image --job JOB_ID --scene 2 --provider openai --allow-paid
```

Use `--model` to override the default hosted model; the chosen model must be supported by your provider account. Hugging Face inference availability and free credits vary; OpenAI Images is separately billed. `--allow-paid` permits potentially billable API requests, **not** a spending cap. No fallback between providers is performed.

## Review and render

```bash
streamlit run src/historyforgeai/interfaces/storyboard_app.py -- workspace/jobs/JOB_ID
historyforgeai render --job JOB_ID
```

Approve each candidate in Streamlit and apply the approved storyboard before rendering. Rendered video has no voiceover unless you separately provide `workspace/jobs/JOB_ID/narration.wav`. Image-generation prompts currently use the scene's `visual_description`. API results and rights are not automatically verified.
