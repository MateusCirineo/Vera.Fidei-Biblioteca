from fastapi import APIRouter
from schemas.citation import VerifyCitationRequest, VerifyCitationResponse
from services.verification_service import VerificationService

router = APIRouter()
service = VerificationService()


@router.post("/verify-citation", response_model=VerifyCitationResponse)
def verify_citation(payload: VerifyCitationRequest) -> VerifyCitationResponse:
    return service.verify(payload)
