import requests

class WikipediaResearch:
    """Wikipedia summary for discovery, not a verified historical source."""
    def collect(self, topic: str) -> str:
        endpoint = "https://en.wikipedia.org/w/api.php"
        params = {"action": "query", "generator": "search", "gsrsearch": topic,
                  "gsrlimit": 3, "prop": "extracts|info", "inprop": "url", "explaintext": 1,
                  "exintro": 1, "format": "json"}
        try:
            r = requests.get(endpoint, params=params, headers={"User-Agent": "HistoryForgeAI/0.1 (educational research)"}, timeout=20)
            r.raise_for_status()
            pages = r.json().get("query", {}).get("pages", {})
            return "\n".join(f"{p.get('title')} ({p.get('fullurl')}): {p.get('extract','')[:2400]}" for p in pages.values())
        except (requests.RequestException, ValueError):
            return "No external research retrieved. All historical claims require verification."
