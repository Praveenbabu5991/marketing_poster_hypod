"""Test fixtures: test DB, mock LLM, FastAPI test client."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


# --- Test database (SQLite in-memory) ---
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    """Create tables and yield a test DB session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with test_session_factory() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session):
    """FastAPI test client with overridden DB dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Test user ---
TEST_USER_ID = uuid.UUID("12345678-1234-1234-1234-123456789012")
TEST_EMAIL = "test@example.com"
TEST_NAME = "Test User"


@pytest.fixture
def test_user_token() -> str:
    """Generate a valid JWT token for testing."""
    payload = {
        "sub": str(TEST_USER_ID),
        "email": TEST_EMAIL,
        "name": TEST_NAME,
        "cognito:groups": ["Hylancer"],
    }
    return jwt.encode(payload, "test-secret", algorithm="HS256")


@pytest.fixture
def auth_headers(test_user_token) -> dict:
    """Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {test_user_token}"}


# --- Mock LLM ---
@pytest.fixture
def mock_llm():
    """Mock BaseChatModel for testing agent graphs."""
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)

    from langchain_core.messages import AIMessage
    llm.invoke = MagicMock(return_value=AIMessage(content="Test response"))
    return llm


# --- Test brand data ---
@pytest.fixture
def sample_brand_data():
    return {
        "name": "TestBrand",
        "industry": "Technology",
        "overview": "A test technology company",
        "tone": "professional",
        "target_audience": "Tech enthusiasts 25-40",
        "products_services": "SaaS platform",
        "logo_path": "/uploads/logos/test_logo.png",
        "colors": ["#1a1a2e", "#16213e", "#e94560"],
        "product_images": [],
        "style_reference_url": None,
    }
