from __future__ import annotations

import datetime
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from core.deps import get_current_user
from models.database import SessionLocal, User, UserFavorite
from schemas.favorite import FavoriteCreate, FavoriteListResponse, FavoriteResponse

router = APIRouter()

ALLOWED_KINDS = {"book", "prayer"}


def _metadata_from_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _favorite_to_response(item: UserFavorite) -> FavoriteResponse:
    return FavoriteResponse(
        id=item.id,
        kind=item.kind,  # type: ignore[arg-type]
        item_id=item.item_id,
        title=item.title,
        subtitle=item.subtitle,
        href=item.href,
        source=item.source,
        metadata=_metadata_from_json(item.metadata_json),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("", response_model=FavoriteListResponse)
def list_favorites(
    kind: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> FavoriteListResponse:
    if kind is not None and kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de favorito invalido.")

    with SessionLocal() as db:
        query = db.query(UserFavorite).filter(UserFavorite.user_id == current_user.id)
        if kind:
            query = query.filter(UserFavorite.kind == kind)
        items = query.order_by(UserFavorite.updated_at.desc(), UserFavorite.id.desc()).all()
        return FavoriteListResponse(
            items=[_favorite_to_response(item) for item in items],
            total=len(items),
        )


@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
def save_favorite(
    payload: FavoriteCreate,
    current_user: User = Depends(get_current_user),
) -> FavoriteResponse:
    now = datetime.datetime.utcnow()
    metadata_json = json.dumps(payload.metadata or {}, ensure_ascii=False) if payload.metadata else None

    with SessionLocal() as db:
        item = (
            db.query(UserFavorite)
            .filter(
                UserFavorite.user_id == current_user.id,
                UserFavorite.kind == payload.kind,
                UserFavorite.item_id == payload.item_id,
            )
            .first()
        )
        if item is None:
            item = UserFavorite(
                user_id=current_user.id,
                kind=payload.kind,
                item_id=payload.item_id,
                title=payload.title,
                subtitle=payload.subtitle,
                href=payload.href,
                source=payload.source,
                metadata_json=metadata_json,
                created_at=now,
                updated_at=now,
            )
            db.add(item)
        else:
            item.title = payload.title
            item.subtitle = payload.subtitle
            item.href = payload.href
            item.source = payload.source
            item.metadata_json = metadata_json
            item.updated_at = now

        db.commit()
        db.refresh(item)
        return _favorite_to_response(item)


@router.delete("/{kind}/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_favorite(
    kind: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    if kind not in ALLOWED_KINDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo de favorito invalido.")

    with SessionLocal() as db:
        item = (
            db.query(UserFavorite)
            .filter(
                UserFavorite.user_id == current_user.id,
                UserFavorite.kind == kind,
                UserFavorite.item_id == item_id,
            )
            .first()
        )
        if item is not None:
            db.delete(item)
            db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
