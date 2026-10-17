# Manual or Gemini script creation

Both paths create the same job format for storyboard review.

## Gemini-generated script

```bash
historyforgeai run --topic "Rajendra Chola vs Chalukyas" --provider gemini --no-render --no-audio
```

## Your own script and scene breakdown

Copy `examples/manual_script.json` and replace the sample narration with your own researched script. Set `duration_seconds` to the desired total and provide each scene's `index`, `duration_seconds`, `narration`, `visual_description`, and `asset_query`.

```bash
cp examples/manual_script.json my_script.json
historyforgeai import-script --file my_script.json
historyforgeai storyboard --job JOB_ID
streamlit run src/historyforgeai/interfaces/storyboard_app.py -- workspace/jobs/JOB_ID
```

The importer validates JSON, sequential scene indexes, total scene durations (within 0.01s), and that scene narrations concatenate to the full narration (ignoring whitespace differences). It creates a planned job without calling Gemini, generating audio, downloading assets, or rendering. Existing Gemini `run` behavior is unchanged.

**Note:** The example text is deliberately short and is **not** a real 60-second voiceover. Duration fields are targets only; measured TTS audio may require scene timing adjustment. All historical claims require editorial verification.
