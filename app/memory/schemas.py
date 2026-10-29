from typing import Optional
from pydantic import BaseModel


class MemoryCandidate(BaseModel):
    category: str           # "profile" | "preferences" | "care_context"
    content: str
    source: Optional[str] = None


class MemoryContext(BaseModel):
    profile: str = ""
    preferences: str = ""
    care_context: str = ""

    def to_prompt_text(self) -> str:
        parts = []
        if self.profile:
            parts.append(f"[User Profile]\n{self.profile}")
        if self.preferences:
            parts.append(f"[User Preferences]\n{self.preferences}")
        if self.care_context:
            parts.append(f"[Care Context]\n{self.care_context}")
        return "\n\n".join(parts)

    def to_task_preferences_text(self) -> str:
        return self.preferences or ""


class MemoryUpdateResult(BaseModel):
    added: int = 0
    skipped: int = 0
