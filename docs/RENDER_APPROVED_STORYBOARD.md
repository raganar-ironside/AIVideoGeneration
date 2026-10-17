# Render an approved storyboard

Install the optional reviewer dependencies:

```bash
python -m pip install -e '.[review,dev]'
```

Workflow:

```bash
historyforgeai run --topic "Ashoka" --provider mock --no-render
historyforgeai storyboard --job JOB_ID
streamlit run src/historyforgeai/interfaces/storyboard_app.py -- workspace/jobs/JOB_ID
# Approve every scene and save the review in Streamlit.
historyforgeai render --job JOB_ID --motion zoom_in
```

The render command requires an existing scene plan, saved storyboard, and an approved local image for **every** scene. It applies the approved images to the existing plan and renders the same job without invoking the LLM or creating another job. If `narration.wav` already exists, it is reused; otherwise the result is silent. This command does not synthesize or align audio, so ensure existing narration matches the scene durations.

The reviewer currently requires manually downloaded local images; Commons search results are candidates, not automatically approved or downloaded. Review image licences and attribution before publishing.
