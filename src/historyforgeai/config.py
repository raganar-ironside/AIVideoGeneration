import json
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

def settings():
    load_dotenv(ROOT / ".env")
    return json.loads((ROOT / "configs" / "development.json").read_text(encoding="utf-8"))
