from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FavoriteKind = Literal["book", "prayer"]


class FavoriteCreate(BaseModel):
    kind: FavoriteKind
    item_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    href: str = Field(min_length=1, max_length=500)
    source: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None


class FavoriteResponse(BaseModel):
    id: int
    kind: FavoriteKind
    item_id: str
    title: str
    subtitle: str | None
    href: str
    source: str | None
    metadata: dict[str, Any] | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class FavoriteListResponse(BaseModel):
    items: list[FavoriteResponse]
    total: int
