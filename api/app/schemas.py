from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class LeadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ShortText
    company: ShortText
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    budget: Decimal = Field(ge=0, le=100_000_000, max_digits=12, decimal_places=2)
    data_label: Literal["DEMO DATA"] = "DEMO DATA"


class Qualification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: Literal["hot", "warm", "cold"]
    score: int = Field(ge=0, le=100, strict=True)
    reasons: list[Reason] = Field(min_length=1, max_length=5)
    suggested_reply: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]

    @model_validator(mode="after")
    def consistent_tier(self) -> "Qualification":
        expected = "hot" if self.score >= 70 else "warm" if self.score >= 40 else "cold"
        if self.tier != expected:
            raise ValueError("Tier must match score: hot >=70, warm >=40, otherwise cold")
        return self


class LeadRead(LeadCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    qualification: Qualification
