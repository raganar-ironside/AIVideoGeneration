"""Gemini native audio generation, saved as mono 24-kHz PCM WAV."""
import os
import wave
from pathlib import Path


class GeminiSpeech:
    def __init__(self, model=None, voice=None):
        self.model = model or os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
        self.voice = voice or os.getenv("GEMINI_TTS_VOICE", "Charon")

    def synthesize(self, text: str, destination: str) -> bool:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Install Gemini TTS: pip install '.[gemini-tts]'") from exc
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is required")
        client = genai.Client(api_key=key)
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=(
                    "Read the following Hindi narration exactly as written. "
                    "Use a deep, resonant, authoritative male documentary voice, "
                    "a measured pace, and clear pronunciation of Sanskrit and historical names. "
                    "Do not add or omit words.\n\n" + text
                ),
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)
                        )
                    ),
                ),
            )
            parts = response.candidates[0].content.parts if response.candidates else []
            audio = next((p.inline_data for p in parts if getattr(p, "inline_data", None)), None)
            if audio is None or not audio.data:
                raise RuntimeError("Gemini returned no audio (check TTS model access and quota)")
            if audio.mime_type and "pcm" not in audio.mime_type.lower():
                raise RuntimeError(f"Unexpected Gemini audio format: {audio.mime_type}")
            output = Path(destination)
            output.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(audio.data)
            return output.stat().st_size > 44
        finally:
            client.close()
