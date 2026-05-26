from fastapi import APIRouter

from app.services.llm.factory import provider_status

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/model-status")
async def model_status() -> dict:
    """Report whether optional model providers are configured.

    This does not expose secret values. It only tells the UI if a provider can
    be tested/used by services that call social_analyzer's LLM polisher.
    """
    return {
        "providers": provider_status()
    }
