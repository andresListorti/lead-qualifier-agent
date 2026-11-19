import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    llm_provider: str = "fixture"
    gemini_api_key: str = field(default="", repr=False)
    gemini_model: str = ""
    gemini_free_tier_confirmed: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///./leads.db"),
            llm_provider=os.getenv("LLM_PROVIDER", "fixture"),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", ""),
            gemini_free_tier_confirmed=os.getenv("GEMINI_FREE_TIER_CONFIRMED") == "true",
        )
