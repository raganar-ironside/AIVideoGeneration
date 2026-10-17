import shutil
import subprocess

class EspeakSpeech:
    def synthesize(self, text: str, destination: str) -> bool:
        if not shutil.which("espeak-ng"):
            return False
        subprocess.run(["espeak-ng", "-v", "en", "-s", "150", "-w", destination, text],
                       check=True, timeout=90, capture_output=True)
        return True
