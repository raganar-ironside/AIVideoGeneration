import os
from pathlib import Path
import requests

class WikimediaAssets:
    """Fetch a Commons thumbnail and preserve attribution metadata; review licences manually."""
    def fetch(self, query: str, destination: str) -> dict | None:
        ua = os.getenv("WIKIMEDIA_USER_AGENT", "HistoryForgeAI/0.1 (contact: example@example.com)")
        headers = {"User-Agent": ua}
        params = {"action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
                  "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
                  "iiurlwidth": 1200, "format": "json"}
        try:
            response = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=headers, timeout=30)
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
            for page in pages.values():
                infos = page.get("imageinfo") or []
                if not infos: continue
                info = infos[0]
                if info.get("mime") not in ("image/jpeg", "image/png", "image/webp"): continue
                url = info.get("thumburl") or info.get("url")
                if not url: continue
                asset = requests.get(url, headers=headers, timeout=45)
                asset.raise_for_status()
                if len(asset.content) > 15_000_000: continue
                dest = Path(destination)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(asset.content)
                meta = info.get("extmetadata", {})
                return {"source_url": info.get("descriptionurl", ""),
                        "license": meta.get("LicenseShortName", {}).get("value", "Unknown"),
                        "attribution": meta.get("Artist", {}).get("value", ""),
                        "title": page.get("title", "")}
        except (requests.RequestException, ValueError, OSError):
            return None
        return None
