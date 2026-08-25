from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.deps import require_min_plan
from models.database import SessionLocal, Institution, InstitutionMember, User, VerificationHistory

router = APIRouter()


class CreateInstitutionRequest(BaseModel):
    name: str


class InviteMemberRequest(BaseModel):
    email: str


class UpdateMemberRoleRequest(BaseModel):
    role: str


def _get_institution_for_user(user: User) -> Institution:
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.admin_user_id == user.id).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Você não possui uma instituição.",
            )
        return inst


@router.post("", status_code=status.HTTP_201_CREATED)
def create_institution(
    payload: CreateInstitutionRequest,
    current_user: User = Depends(require_min_plan("patristico")),
) -> dict:
    with SessionLocal() as db:
        existing = db.query(Institution).filter(Institution.admin_user_id == current_user.id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Você já possui uma instituição registrada.",
            )
        inst = Institution(
            name=payload.name,
            admin_user_id=current_user.id,
        )
        db.add(inst)
        db.flush()
        # Admin is also a member
        member = InstitutionMember(
            institution_id=inst.id,
            user_id=current_user.id,
            role="admin",
        )
        db.add(member)
        db.commit()
        db.refresh(inst)
        return {
            "id": inst.id,
            "name": inst.name,
            "admin_user_id": inst.admin_user_id,
            "created_at": inst.created_at.isoformat() if inst.created_at else None,
        }


@router.get("")
def get_institution(
    current_user: User = Depends(require_min_plan("patristico")),
) -> dict:
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.admin_user_id == current_user.id).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Você não possui uma instituição.",
            )
        return {
            "id": inst.id,
            "name": inst.name,
            "admin_user_id": inst.admin_user_id,
            "created_at": inst.created_at.isoformat() if inst.created_at else None,
        }


@router.get("/membros")
def list_members(
    current_user: User = Depends(require_min_plan("patristico")),
) -> dict:
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.admin_user_id == current_user.id).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Você não possui uma instituição.",
            )
        members = (
            db.query(InstitutionMember)
            .filter(InstitutionMember.institution_id == inst.id)
            .all()
        )
        result = []
        for m in members:
            user = db.get(User, m.user_id)
            result.append({
                "id": m.id,
                "user_id": m.user_id,
                "name": user.name if user else None,
                "email": user.email if user else None,
                "role": m.role,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            })
    return {"institution_id": inst.id, "members": result}


@router.post("/convidar", status_code=status.HTTP_201_CREATED)
def invite_member(
    payload: InviteMemberRequest,
    current_user: User = Depends(require_min_plan("patristico")),
) -> dict:
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.admin_user_id == current_user.id).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Você não possui uma instituição.",
            )
        target_user = db.query(User).filter(User.email == payload.email).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado com este e-mail.",
            )
        already = (
            db.query(InstitutionMember)
            .filter(
                InstitutionMember.institution_id == inst.id,
                InstitutionMember.user_id == target_user.id,
            )
            .first()
        )
        if already:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuário já é membro desta instituição.",
            )
        member = InstitutionMember(
            institution_id=inst.id,
            user_id=target_user.id,
            role="membro",
        )
        db.add(member)
        db.commit()
    return {"detail": f"Usuário '{payload.email}' adicionado com sucesso."}


@router.patch("/membros/{member_id}")
def update_member_role(
    member_id: int,
    payload: UpdateMemberRoleRequest,
    current_user: User = Depends(require_min_plan("patristico")),
) -> dict:
    role = payload.role.strip().lower()
    if role not in {"admin", "membro"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Papel invalido. Use 'admin' ou 'membro'.",
        )
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.admin_user_id == current_user.id).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Você não possui uma instituição.",
            )
        member = (
            db.query(InstitutionMember)
            .filter(
                InstitutionMember.id == member_id,
                InstitutionMember.institution_id == inst.id,
            )
            .first()
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membro não encontrado.")
        if member.user_id == current_user.id and role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O administrador principal deve permanecer como admin.",
            )
        member.role = role
        db.commit()
        db.refresh(member)
        user = db.get(User, member.user_id)
        return {
            "id": member.id,
            "user_id": member.user_id,
            "name": user.name if user else None,
            "email": user.email if user else None,
            "role": member.role,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
        }


@router.delete("/membros/{member_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def remove_member(
    member_id: int,
    current_user: User = Depends(require_min_plan("patristico")),
) -> None:
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.admin_user_id == current_user.id).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Você não possui uma instituição.",
            )
        member = (
            db.query(InstitutionMember)
            .filter(
                InstitutionMember.id == member_id,
                InstitutionMember.institution_id == inst.id,
            )
            .first()
        )
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membro não encontrado.")
        if member.user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não é possível remover o administrador principal.",
            )
        db.delete(member)
        db.commit()


@router.get("/relatorio")
def get_relatorio(
    current_user: User = Depends(require_min_plan("patristico")),
) -> dict:
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.admin_user_id == current_user.id).first()
        if not inst:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Você não possui uma instituição.",
            )
        members = (
            db.query(InstitutionMember)
            .filter(InstitutionMember.institution_id == inst.id)
            .all()
        )
        member_user_ids = [m.user_id for m in members]

        now = datetime.datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        verifications = (
            db.query(VerificationHistory)
            .filter(
                VerificationHistory.user_id.in_(member_user_ids),
                VerificationHistory.created_at >= month_start,
            )
            .all()
        )

        total = len(verifications)
        distribution: dict[str, int] = {}
        by_member: dict[int, dict] = {}
        for member in members:
            member_user = db.get(User, member.user_id)
            by_member[member.user_id] = {
                "user_id": member.user_id,
                "name": member_user.name if member_user else None,
                "email": member_user.email if member_user else None,
                "role": member.role,
                "total_verificacoes": 0,
                "distribuicao_vereditos": {},
            }
        for v in verifications:
            key = v.label or "Sem classificação"
            distribution[key] = distribution.get(key, 0) + 1
            member_report = by_member.get(v.user_id)
            if member_report:
                member_report["total_verificacoes"] += 1
                member_distribution = member_report["distribuicao_vereditos"]
                member_distribution[key] = member_distribution.get(key, 0) + 1

    return {
        "institution_id": inst.id,
        "institution_name": inst.name,
        "period": month_start.strftime("%Y-%m"),
        "total_verificacoes": total,
        "distribuicao_vereditos": distribution,
        "membros": list(by_member.values()),
    }
