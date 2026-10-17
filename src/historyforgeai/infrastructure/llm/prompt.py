from historyforgeai.domain.models import ShortPlan

def build_prompt(topic: str, context: str, duration: int, scenes: int) -> str:
    return f"""You write accurate, engaging, English-language Indian history documentary Shorts.
Topic: {topic}
Target duration: {duration} seconds. Exactly {scenes} scenes. Scene indices 1..{scenes}.
Return ONLY JSON matching this JSON schema: {ShortPlan.model_json_schema()}
Use the supplied source notes where possible. Never invent source URLs or imply historical
reconstructions are authentic footage. If sources are absent, claims must have verified=false
and source_urls=[]. Keep narration concise and spoken-friendly. Sum scene durations to
approximately {duration} seconds. For each scene provide visual_description and asset_query
suitable for Wikimedia Commons. Set all claims verified=false; editorial review is mandatory.
Source notes (unverified until human review): {context[:14000]}
"""
