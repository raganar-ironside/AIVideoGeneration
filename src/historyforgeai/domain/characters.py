from pydantic import BaseModel, Field

class Character(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    display_name: str
    universe: str
    description: str = ""
    canonical_image: str | None = None
    approved: bool = False
    notes: str = ""
