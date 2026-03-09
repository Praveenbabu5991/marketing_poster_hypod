# Marketing Poster Hypod

AI-powered social media content creation platform with 6 specialized agents for generating branded marketing content.

## Agents

| Agent | Description |
|-------|-------------|
| **Single Post** | Create a branded social media post with image, caption, and hashtags |
| **Carousel** | Multi-slide Instagram carousel with consistent branding |
| **Campaign** | Plan and generate a multi-week social media campaign |
| **Sales Poster** | Product sales posters with pricing, discounts, and CTAs |
| **Motion Graphics** | Short branded motion graphics videos |
| **Product Video** | Product showcase videos from product images |

## Tech Stack

- **Backend**: FastAPI + LangGraph + LangChain (model-agnostic)
- **Frontend**: React 19 + TypeScript + Tailwind CSS v4 + Vite
- **Database**: PostgreSQL
- **AI Models**: Gemini (default), OpenAI, Anthropic (configurable)

## Quick Start with Docker

### Prerequisites

- Docker and Docker Compose
- A Google API key (for Gemini models)

### 1. Clone and configure

```bash
git clone https://github.com/Praveenbabu5991/marketing_poster_hypod.git
cd marketing_poster_hypod
cp env.example backend/.env
```

Edit `backend/.env` and add your API key:
```
GOOGLE_API_KEY=your-google-api-key-here
```

### 2. Build and start

```bash
make up
```

This single command will:
1. Build Docker images for backend and frontend
2. Start PostgreSQL, Backend, and Frontend containers
3. Run database migrations automatically on first start

Services:
- **Frontend** — [http://localhost:3000](http://localhost:3000)
- **Backend API** — http://localhost:8000
- **PostgreSQL** — localhost:5432

### 3. Open the app

Navigate to [http://localhost:3000](http://localhost:3000)

1. Create a brand (name, logo, colors, tone)
2. Select an agent (Single Post, Carousel, Campaign, etc.)
3. Start chatting — the agent generates content with your brand identity

### 4. Stop

```bash
make down
```

## Local Development (without Docker)

### Prerequisites

- Python 3.12+
- Node.js 22+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- PostgreSQL running locally

### Setup

```bash
# Install all dependencies
make setup

# Configure environment
cp env.example backend/.env
# Edit backend/.env with your API key and DB credentials

# Run database migrations
make migrate

# Start both servers
make dev
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000

## Makefile Commands

```
make help           Show all available commands
make setup          Install all dependencies (backend + frontend)
make dev            Start both backend and frontend for local development
make dev-backend    Start backend dev server (port 8000)
make dev-frontend   Start frontend dev server (port 3000)
make test           Run backend tests
make test-cov       Run backend tests with coverage
make migrate        Run database migrations
make build          Build all Docker images
make up             Build + start all services + run migrations
make down           Stop all services
make logs           Follow backend logs
make logs-all       Follow all service logs
make restart        Rebuild and restart all services
make clean          Remove caches and build artifacts
```

## Project Structure

```
├── backend/
│   ├── agents/              # 6 agent implementations (graphs + prompts + tools)
│   ├── app/
│   │   ├── api/v1/          # REST + SSE endpoints
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # Business logic + streaming
│   │   └── security/        # JWT auth
│   ├── brand/               # Brand context injection
│   ├── tests/               # 57 tests (unit + integration)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/             # API client + SSE streaming
│   │   ├── components/      # React components
│   │   ├── hooks/           # useChat SSE hook
│   │   ├── pages/           # Dashboard, BrandSetup, Chat
│   │   └── store/           # Zustand state
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── Makefile
└── env.example
```
