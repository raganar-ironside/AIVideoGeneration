# Narration providers

Speech uses **eSpeak** if no provider is configured; the supplied `.env.example` sets `SPEECH_PROVIDER=auto` to try Kokoro ONNX locally, then Edge TTS online, then eSpeak. Start with the [beginner user journey](USER_JOURNEY.md).

## Install

```bash
pip install -e '.[kokoro,edge]'
sudo apt-get install ffmpeg espeak-ng
```

Download `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases) into `models/` (or set explicit paths). Model files are not committed.

## Configuration

```dotenv
SPEECH_PROVIDER=auto
SPEECH_FALLBACK_ORDER=kokoro,edge,espeak
KOKORO_MODEL=models/kokoro-v1.0.onnx
KOKORO_VOICES=models/voices-v1.0.bin
KOKORO_VOICE=hm_omega
KOKORO_LANG=hi
KOKORO_SPEED=0.9
VOICE_PRESET=documentary
# Optional overrides: VOICE_SPEED, VOICE_PITCH_SEMITONES,
# VOICE_BASS_DB, VOICE_SENTENCE_PAUSE
EDGE_TTS_VOICE=hi-IN-MadhurNeural
EDGE_TTS_RATE=-8%
```

## Voice presets

Choose `VOICE_PRESET=normal`, `documentary`, or `epic`. Presets set narration speed, pitch, bass enhancement, and Kokoro sentence pauses. You can override individual values using `VOICE_SPEED`, `VOICE_PITCH_SEMITONES`, `VOICE_BASS_DB`, and `VOICE_SENTENCE_PAUSE`. When using `build_speech()`, `VOICE_SPEED` takes precedence over `KOKORO_SPEED`; the preset default is used when `VOICE_SPEED` is absent. Pitch/bass processing requires FFmpeg and is applied after successful provider synthesis. The Kokoro sentence pause control is not applied to Edge or eSpeak. Edge rate is calculated from the selected preset speed when constructed by the factory. The eSpeak adapter currently uses a fixed speaking rate. Always listen to samples before publishing.

**Hindi caveat:** Kokoro ONNX language and Hindi voice support depend on the particular model, voice bundle, and phonemizer. Test the chosen voice with Devanagari text; if it fails, automatic mode tries Edge. Do not assume every Kokoro distribution supports Hindi.

The Edge adapter uses an unofficial online endpoint and requires internet access. Verify usage rights before publishing or monetizing generated narration. The fallback emits warnings on provider failures and raises a clear error if every provider fails. For per-scene timing, run with `--scene-audio`.

The WAV output from each provider is compatible with the FFmpeg renderer. Generating locally does not require Google Cloud billing.
