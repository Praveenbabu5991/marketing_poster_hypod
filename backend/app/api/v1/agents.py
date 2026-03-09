"""Agent listing endpoint."""

from fastapi import APIRouter

from agents.registry import AGENT_CONFIGS

router = APIRouter()


@router.get("")
async def list_agents():
    """List available agents with metadata."""
    return [
        {"id": key, **config}
        for key, config in AGENT_CONFIGS.items()
    ]
