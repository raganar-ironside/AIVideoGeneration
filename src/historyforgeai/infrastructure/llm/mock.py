from historyforgeai.domain.models import ShortPlan, Scene, Claim

class MockLLM:
    """Deterministic pipeline fixture, NOT a factual research or production script."""
    def create_plan(self, topic: str, context: str, duration: int, scenes: int) -> ShortPlan:
        segments = [
            f"Today we explore {topic}, a fascinating chapter in India's past.",
            "To understand the story, we need to examine the evidence left behind.",
            "Historical inscriptions, monuments, and accounts offer different perspectives.",
            "Some familiar details come from later traditions and remain debated.",
            "We should distinguish documented events from artistic reconstruction.",
            "Explore primary sources and trusted scholarship to learn more."
        ]
        generated = [Scene(index=i+1, duration_seconds=duration/scenes,
            narration=segments[i % len(segments)], visual_description=f"Documentary archival visual for {topic}, section {i+1}",
            asset_query=f"{topic} historical monument inscription", visual_type="historical_artifact") for i in range(scenes)]
        return ShortPlan(topic=topic, title=topic, narration=" ".join(s.narration for s in generated),
            claims=[Claim(statement=f"Historical claims about {topic} require source verification.")], scenes=generated)
