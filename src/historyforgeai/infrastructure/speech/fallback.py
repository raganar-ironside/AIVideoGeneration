"""Ordered, resilient speech synthesis with output validation."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FallbackSpeech:
    def __init__(self, providers):
        if not providers:
            raise ValueError("At least one speech provider is required")
        self.providers = providers

    def synthesize(self, text: str, destination: str) -> bool:
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        errors = []
        for name, provider in self.providers:
            output.unlink(missing_ok=True)
            try:
                if provider.synthesize(text, str(output)) and output.is_file() and output.stat().st_size > 44:
                    logger.info("Speech synthesized with %s", name)
                    return True
                errors.append(f"{name}: no valid audio output")
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                logger.warning("Speech provider %s failed: %s", name, exc)
            output.unlink(missing_ok=True)
        raise RuntimeError("All speech providers failed: " + "; ".join(errors))
