"""Centralized configuration: env vars, model names, paths, tracing."""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from backend root (cwd when running uvicorn)
_backend_root = Path(__file__).parent.parent
_project_root = _backend_root.parent
load_dotenv(_backend_root / ".env")

# --- Database ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://agent_factory:agent_factory@localhost:5432/agent_factory",
)
# Sync URL for Alembic
DATABASE_URL_SYNC = DATABASE_URL.replace("+asyncpg", "").replace(
    "postgresql://", "postgresql+psycopg2://"
) if "+asyncpg" in DATABASE_URL else DATABASE_URL

# psycopg3 connection string for LangGraph AsyncPostgresSaver
# Strips the +asyncpg driver suffix to get plain postgresql:// URI
CHECKPOINT_URL = DATABASE_URL.replace("+asyncpg", "")

# --- API Keys ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- Google Cloud / Vertex AI ---
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
GCLOUD_PROJECT = os.getenv("GCLOUD_PROJECT", "")
GCLOUD_LOCATION = os.getenv("GCLOUD_LOCATION", "us-central1")

# --- Model Configuration (model-agnostic: provider/model-name) ---
ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "google_genai/gemini-2.5-flash")
IDEA_MODEL = os.getenv("IDEA_MODEL", "google_genai/gemini-2.5-flash")
WRITER_MODEL = os.getenv("WRITER_MODEL", "google_genai/gemini-2.5-flash")
CAPTION_MODEL = os.getenv("CAPTION_MODEL", "gemini-2.5-flash")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gemini-3-pro-image-preview")
EDIT_MODEL = os.getenv("EDIT_MODEL", "gemini-3-pro-image-preview")
VIDEO_MODEL = os.getenv("VIDEO_MODEL", "veo-3.1-generate-001")

# --- Paths ---
GENERATED_DIR = Path(os.getenv("GENERATED_DIR", str(_project_root / "generated")))
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(_project_root / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Server ---
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# --- CORS ---
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# --- LangSmith Tracing ---
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "agent-factory-v4")


# --- Vertex AI / Gemini Pricing (USD) ---
VERTEX_PRICING = {
    # Gemini 2.5 Flash text (doubles above 128K context)
    "gemini-2.5-flash": {"input_per_million": 0.30, "output_per_million": 2.50},
    # Gemini 2.5 Flash Image — $0.039/image at 1K resolution
    "gemini-2.5-flash-image": {"per_image": 0.039},
    # Gemini image generation model
    "gemini-3-pro-image-preview": {"per_image": 0.039},
    # Veo 3.1 Standard — $0.40/sec
    "veo-3.1-generate-001": {"per_second": 0.40},
    # Veo 3.1 Fast — $0.15/sec
    "veo-3.1-fast-generate-001": {"per_second": 0.15},
}


def calculate_cost(
    model_name: str,
    action_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    unit_count: int = 1,
    video_duration_seconds: int = 0,
) -> float:
    """Calculate USD cost for a single API call based on model pricing."""
    # Strip provider prefix (e.g. "google_genai/gemini-2.5-flash" -> "gemini-2.5-flash")
    short_name = model_name.split("/")[-1] if "/" in model_name else model_name
    pricing = VERTEX_PRICING.get(short_name)
    if not pricing:
        return 0.0

    # Video billing — per second
    if "per_second" in pricing:
        duration = video_duration_seconds or 0
        return round(pricing["per_second"] * duration, 6)

    # Image billing — per image
    if "per_image" in pricing:
        return round(pricing["per_image"] * (unit_count or 1), 6)

    # Text billing — per million tokens
    input_cost = (prompt_tokens or 0) / 1_000_000 * pricing.get("input_per_million", 0)
    output_cost = (completion_tokens or 0) / 1_000_000 * pricing.get("output_per_million", 0)
    return round(input_cost + output_cost, 6)


def get_genai_client():
    """Create a google.genai.Client using service account (Vertex AI) or API key."""
    from google import genai
    if GOOGLE_SERVICE_ACCOUNT_FILE and os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        logger.warning("[GOOGLE] Using Vertex AI service account -> project=%s location=%s", GCLOUD_PROJECT, GCLOUD_LOCATION)
        return genai.Client(
            vertexai=True,
            project=GCLOUD_PROJECT,
            location=GCLOUD_LOCATION,
            credentials=creds,
        )
    if GOOGLE_API_KEY:
        logger.warning("[GOOGLE] Using API key (free tier)")
        return genai.Client(api_key=GOOGLE_API_KEY)
    raise RuntimeError("No Google credentials configured")


def get_google_credentials():
    """Get credentials + project for LangChain init_chat_model (Vertex AI)."""
    if GOOGLE_SERVICE_ACCOUNT_FILE and os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        from google.oauth2.service_account import Credentials
        return Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        ), GCLOUD_PROJECT
    return None, None


def setup_tracing():
    """Configure LangSmith tracing for LangGraph."""
    if LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
        print(f"[TRACING] LangSmith enabled -> project={LANGSMITH_PROJECT}")
