# Telegram Memory Bot

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![aiogram](https://img.shields.io/badge/Telegram-aiogram_3-2CA5E0.svg)
![Graphiti](https://img.shields.io/badge/Knowledge_Graph-Graphiti-7928CA.svg)
![Neo4j](https://img.shields.io/badge/Graph_DB-Neo4j_5-008CC1.svg)
![Redis](https://img.shields.io/badge/Cache-Redis_7-DC382D.svg)
![PostgreSQL](https://img.shields.io/badge/RDBMS-PostgreSQL_16-336791.svg)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)
![React](https://img.shields.io/badge/UI-React_18_+_VisNetwork-61DAFB.svg)

Telegram group chat memory bot with episodic knowledge graph extraction, sliding-window
conversational context, dual-chat topology, and an interactive web dashboard for real-time
memory inspection and sandbox dialogue simulation.

## How it works

```mermaid
%%{init: {
  'theme': 'base',
  'flowchart': { 'curve': 'basis', 'nodeSpacing': 45, 'rankSpacing': 65, 'wrap': true },
  'themeVariables': {
    'fontSize': '14px',
    'primaryColor': '#37474F',
    'primaryTextColor': '#ffffff',
    'primaryBorderColor': '#78909C',
    'lineColor': '#90A4AE',
    'secondaryColor': '#37474F',
    'tertiaryColor': '#37474F'
  }
}}%%
flowchart LR
    subgraph Telegram["Telegram Platform"]
        direction TB
        Group(["Group Chat<br/>GROUP_CHAT_ID"])
        Admin(["Admin Private<br/>ADMIN_USER_ID"])
        BotAPI["Telegram Bot API<br/>aiogram 3"]

        Group <-->|Poll / Updates| BotAPI
        Admin <-->|Poll / Updates| BotAPI
    end

    subgraph BotApp["Core Bot Application"]
        direction TB
        Router["Telegram Router<br/>Filters & Media"]
        Debounce["Message Debouncer<br/>10s sliding / 30s max"]
        Filter["Noise Filter<br/>Stopwords & Regex"]
        Context["Context Builder<br/>Sliding Window"]
        Response["Response Service<br/>Prompt & Sanitizer"]
        Notifier["Admin Notifier<br/>Async Alerts"]

        Router -->|Chat messages| Context
        Router -->|Consecutive stream| Debounce
        Debounce -->|Flushed batches| Filter
        Router -->|Mention / Reply| Response
        Response -->|Error alerts| Notifier
    end

    subgraph Storage["Storage & Intelligence Layer"]
        direction TB
        Postgres[(PostgreSQL 16<br/>Chat Members)]
        RedisCache[(Redis 7<br/>Context Buffer)]
        Neo4jGraph[(Neo4j 5<br/>Graphiti KG)]
        OpenAI["OpenAI API<br/>LLM + Embeddings"]

        Router -->|Upsert member| Postgres
        Context <-->|Recent buffer| RedisCache
        Filter -->|Ingest episodes| Neo4jGraph
        Response <-->|Facts & Entities| Neo4jGraph
        Response <-->|Completions| OpenAI
        Neo4jGraph <-->|Embeddings| OpenAI
    end

    subgraph Web["Dashboard & Simulation"]
        direction TB
        API["FastAPI REST API<br/>Uvicorn"]
        Dashboard["React Dashboard<br/>Vis-Network Graph"]
        Sandbox["Chat Sandbox<br/>Simulator Engine"]

        Dashboard <-->|REST / JSON| API
        API <-->|Live Graph & Stats| Neo4jGraph
        API <-->|Active Context| RedisCache
        Sandbox -->|Virtual messages| Response
    end

    BotAPI --> Router
    Response -->|Safe reply| BotAPI
    Notifier -->|Alerts| BotAPI

    classDef core fill:#1565C0,stroke:#90CAF9,stroke-width:1.5px,color:#ffffff
    classDef app fill:#2E7D32,stroke:#A5D6A7,stroke-width:1.5px,color:#ffffff
    classDef storage fill:#37474F,stroke:#90A4AE,stroke-width:1.5px,color:#ffffff
    classDef web fill:#AD1457,stroke:#F48FB1,stroke-width:1.5px,color:#ffffff

    class Group,Admin,BotAPI core
    class Router,Debounce,Filter,Context,Response,Notifier app
    class Postgres,RedisCache,Neo4jGraph,OpenAI storage
    class API,Dashboard,Sandbox web

    style Telegram fill:none,stroke:#78909C,stroke-width:1px,color:#90A4AE
    style BotApp fill:none,stroke:#78909C,stroke-width:1px,color:#90A4AE
    style Storage fill:none,stroke:#78909C,stroke-width:1px,color:#90A4AE
    style Web fill:none,stroke:#78909C,stroke-width:1px,color:#90A4AE
```

- **Dual-Chat Topology**: Operates across a designated group chat (`GROUP_CHAT_ID`) for read/write
  episodic memory accumulation, and a private admin channel (`ADMIN_USER_ID`) for read-only
  queries into group knowledge with isolated private conversation context.
- **Short-Term Context**: `ContextBuilder` maintains a Redis-backed sliding window of recent
  messages (last 15 minutes, minimum 10 messages) preserving multi-turn dialogue continuity.
- **Message Debouncing**: `MessageDebouncer` aggregates consecutive messages from the same speaker
  in memory with a 10s sliding window (capped at 30s maximum) before batch ingestion into the graph.
- **Noise Filtering**: `MessageNoiseFilter` drops conversational filler, one-word replies, commands,
  and uncaptioned stickers before ingestion. Rules are configurable via `prompts/noise_filter.json`.
- **Episodic Knowledge Graph**: `MemoryService` and `GraphitiMemoryBackend` extract entities
  (`Person`, `Animal`, `Item`, `Location`, `Concept`) and temporal relationships into Neo4j.
- **Response Orchestration**: `ResponseService` combines persona prompts, Level 1 user quick facts,
  Level 2 semantic memories, and recent context to generate responses via OpenAI.
- **Dashboard & Sandbox**: FastAPI backend (`/api/`) and React frontend (`frontend/`) visualizes
  the interactive knowledge graph using Vis-Network, tracks system health, and provides a sandbox
  chat simulator for regression testing without Telegram.

---

## Requirements

- Linux, macOS, or Windows
- Python 3.12+ (pinned in `.python-version`), [uv](https://docs.astral.sh/uv/) package manager
- Docker & Docker Compose (for PostgreSQL, Redis, Neo4j, or full-stack containerization)
- Node.js 20+ and npm (for frontend dashboard development and builds)
- OpenAI API Key & Telegram Bot Token (from [@BotFather](https://t.me/botfather))

---

## Setup

### Full Stack (Docker Compose)

The recommended way to run the entire bot, databases, and web dashboard in production:

```bash
# 1. Clone repository
git clone https://github.com/0resuto/tg-bot.git
cd tg-bot

# 2. Configure environment variables
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, and credentials

# 3. Create persona prompt
cp prompts/system_prompt.example.md prompts/system_prompt.md

# 4. Build and start containers
docker compose up -d --build
```

Services started:
- `bot`: Runs Alembic migrations (`alembic upgrade head`) and polls Telegram updates.
- `dashboard`: Serves the REST API and React UI on `http://127.0.0.1:8080` (or configured `WEB_PORT`).
- `postgres`: PostgreSQL 16 database for member identities.
- `redis`: Redis 7 in-memory store for context buffers.
- `neo4j`: Neo4j 5 Community Edition with Graphiti episodic knowledge graph.

### Local Development (Windows)

For local development on Windows, use the interactive helper `dev.bat`:

```cmd
dev.bat
```

The menu provides:
1. `Start Databases in Docker` — starts PostgreSQL, Redis, and Neo4j via Docker Compose.
2. `Start Control Panel` — starts FastAPI backend on `:8080` + Vite HMR on `:3000`.
3. `Start Dev Chat Simulator` — starts backend in `--simulator` mode + Vite HMR on `:3000`.
4. `Stop Docker Stack` — shuts down database containers.
5. `Run Tests and Linters` — executes `ruff` and `pytest`.

### Manual Commands

```bash
# Install dependencies
uv sync --extra dev

# Run database migrations
uv run alembic upgrade head

# Start Telegram bot
uv run python -m bot

# Start Web Dashboard
uv run python -m bot.api --host 127.0.0.1 --port 8080

# Start Web Dashboard in Simulator Sandbox mode
uv run python -m bot.api --host 127.0.0.1 --port 8080 --simulator
```

---

## Configuration

All configuration is managed through environment variables via Pydantic Settings (`src/bot/config.py`).
Variables are loaded from `.env`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | *required* | Telegram bot token from @BotFather |
| `TELEGRAM_PROXY_URL` | *(empty)* | Optional proxy for Telegram API calls, e.g. `socks5://host:1080` or `http://user:pass@host:3128`. Empty = direct connection |
| `GROUP_CHAT_ID` | `0` | Primary group chat ID where episodic memory is collected |
| `ADMIN_USER_ID` | `0` | Telegram user ID authorized for private admin queries |
| `ADMIN_CHAT_ID` | `0` | Optional chat ID for error alerts and notifications |
| `OPENAI_API_KEY` | *required* | OpenAI API Key for embeddings and completions |
| `OPENAI_RESPONSE_MODEL`| `gpt-4o` | Model used for conversation replies |
| `OPENAI_RESPONSE_MAX_TOKENS` | `1500` | Maximum completion tokens per reply (includes reasoning tokens) |
| `OPENAI_EXTRACTION_MODEL`| `gpt-4o-mini` | Model used by Graphiti for entity/relation extraction |
| `OPENAI_EMBEDDING_MODEL`| `text-embedding-3-small` | Model used for vector embeddings |
| `POSTGRES_HOST` | `postgres` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `tgbot` | Database name |
| `POSTGRES_USER` | `tgbot` | Database username |
| `POSTGRES_PASSWORD` | *required* | Database password |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `NEO4J_URI` | `bolt://neo4j:7687` | Neo4j Bolt connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | *required* | Neo4j password |
| `BOT_NAMES` | `Bot` | Comma-separated names the bot responds to (e.g. `Bot, Ista`) |
| `BOT_PERSONA_PROMPT_FILE` | `prompts/system_prompt.md` | Path to persona prompt markdown file |
| `BOT_TIMEZONE` | `Europe/Moscow` | IANA timezone for dates in prompts and relative periods (`за неделю`, `last month`) |
| `DEBOUNCE_SECONDS` | `10.0` | Sliding window in seconds for message debouncing |
| `CONTEXT_WINDOW_MINUTES`| `15` | Minutes of conversation kept in recent context |
| `CONTEXT_MIN_MESSAGES` | `10` | Minimum messages guaranteed in recent context buffer |
| `WEB_HOST` | `127.0.0.1` | Dashboard bind address |
| `WEB_PORT` | `8080` | Dashboard web port |
| `WEB_ENABLE_SIMULATOR` | `false` | Enable chat sandbox endpoint in dashboard |
| `DEBUG` | `false` | Enable verbose debug logging |

### Telegram Proxy (Optional)

aiogram does not read `HTTP_PROXY`/`HTTPS_PROXY`, so Telegram API traffic is
routed through `TELEGRAM_PROXY_URL` when it is set. Supported schemes are
`http://`, `socks4://` and `socks5://`, optionally with credentials included in
the URL. Leave the variable empty for a direct connection — nothing else needs
to be configured.

```bash
# .env
TELEGRAM_PROXY_URL=socks5://127.0.0.1:1080
```

Notes:
- OpenAI/Graphiti calls go through `httpx`, which honors `HTTP_PROXY`/`HTTPS_PROXY`
  automatically. Set those separately if LLM traffic also needs a proxy.
- In Docker, `127.0.0.1` inside the `bot` container refers to the container itself.
  Point the proxy at an address reachable from the `botnet` network, e.g. a proxy
  container joined to `botnet`, or the host with the proxy listening on `0.0.0.0`
  plus a firewall rule for the Docker subnet.

---

## Web Dashboard & REST API

The dashboard serves a single-page React application and REST API:

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Single-Page Application (React + Vis-Network) |
| `/docs` | `GET` | Interactive Swagger API documentation |
| `/api/health` | `GET` | Health checks for PostgreSQL, Redis, Neo4j, and OpenAI |
| `/api/stats` | `GET` | Operational metrics, node counts, and model info |
| `/api/chats` | `GET` | List recorded chats and group IDs |
| `/api/graph` | `GET` | Graphiti nodes and edges formatted for Vis.js visualization |
| `/api/memories` | `GET` | Extracted facts and temporal relations by chat |
| `/api/context` | `GET` | Current Redis sliding-window messages for a chat |
| `/api/logs` | `GET` | Diagnostic circular buffer of events and errors |
| `/api/simulator/presets` | `GET` | Test users and scenario presets for sandbox |
| `/api/simulator/send_message` | `POST` | Inject a virtual chat message (guarded by `WEB_ENABLE_SIMULATOR`) |

---

## Layout

```text
tg-bot/
├── src/bot/
│   ├── api/                    # FastAPI server, REST router, and dependency container
│   │   ├── services/           # Graph visualizer, memory query, health, simulator
│   │   ├── dependencies.py     # WebContainer wiring and lifecycle
│   │   ├── router.py           # Consolidated API endpoints
│   │   └── server.py           # Uvicorn app factory & SPA static file serving
│   ├── db/                     # Persistence layer
│   │   ├── engine.py           # Async SQLAlchemy engine & session maker
│   │   ├── graphiti.py         # Graphiti Neo4j backend & custom entity models
│   │   ├── redis.py            # Async Redis connection pool
│   │   ├── repository.py       # MemberRepository for chat identity tracking
│   │   └── tables.py           # Declarative ORM models (chats, chat_members)
│   ├── services/               # Core business logic
│   │   ├── admin_notifier.py   # Telegram admin alert dispatcher with HTML formatting
│   │   ├── context_builder.py  # Redis sliding-window conversation buffer
│   │   ├── debouncer.py        # Per-user sliding message aggregator
│   │   ├── llm.py              # OpenAILLMProvider client wrapper
│   │   ├── memory_service.py   # Orchestrator for graph ingestion and query
│   │   ├── mention_detector.py # Mention, transliteration, and reply detection
│   │   ├── message_filter.py   # Heuristic conversational noise filter
│   │   └── response_service.py # Prompt builder, sanitizer, and response pipeline
│   ├── telegram/               # Telegram I/O (aiogram 3)
│   │   ├── handlers/           # Group chat and admin private routers
│   │   ├── dispatcher.py       # Aiogram Dispatcher & Redis storage setup
│   │   ├── filters.py          # Chat type and admin authorization filters
│   │   ├── media.py            # Media extraction (photos, voice, stickers)
│   │   └── middlewares.py      # Dependency injection middleware
│   ├── app.py                  # Application lifecycle and graceful shutdown
│   ├── config.py               # Pydantic Settings configuration
│   ├── log.py                  # Structlog JSON / console logging setup
│   └── models.py               # Domain models and dataclasses
├── frontend/                   # React + TypeScript + Vite dashboard
│   ├── src/components/         # Header, Sidebar, MetricCard, HealthBadge
│   ├── src/views/              # KnowledgeGraph, Memories, Context, Simulator, Logs
│   └── package.json            # Vite, TailwindCSS, Vis-Network dependencies
├── alembic/                    # Database migrations
│   └── versions/               # 0001_initial_schema.py
├── prompts/                    # Prompts and persona templates
│   ├── noise_filter.json       # Heuristic noise filter stopword dictionary
│   └── system_prompt.example.md# Example persona prompt
├── scripts/                    # CLI launchers for dashboard and simulator
├── tests/                      # Pytest test suite (137 unit and integration tests)
├── dev.bat                     # Windows developer control console
├── docker-compose.yml          # Production multi-container composition
├── Dockerfile                  # Multi-stage production container build
├── pyproject.toml              # Project dependencies, ruff, mypy, and pytest config
└── uv.lock                     # Deterministic dependency lockfile
```

---

## Development & Quality Assurance

All linters, type checks, and tests run locally and in GitHub Actions CI (`.github/workflows/ci.yml`):

```bash
# Backend linting and code formatting
uv run ruff check src/ tests/ scripts/ alembic/
uv run ruff format --check .

# Strict static type checking
uv run mypy src/bot

# Run test suite with code coverage check (80% minimum gate)
uv run pytest --cov=bot

# Frontend checks
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build

# Install pre-commit hooks
uv run pre-commit install
```

---

## Production Deployment Runbook

1. **Provision VPS & Docker**: Install Docker Engine and Docker Compose v2.
2. **Clone & Configure**:
   ```bash
   git clone https://github.com/0resuto/tg-bot.git
   cd tg-bot
   cp .env.example .env
   cp prompts/system_prompt.example.md prompts/system_prompt.md
   ```
3. **Configure Secrets**: In `.env`, configure:
   - Strong, unique passwords for `POSTGRES_PASSWORD` and `NEO4J_PASSWORD`.
   - Your `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY`.
   - Your `GROUP_CHAT_ID` and `ADMIN_USER_ID`.
4. **Deploy Stack**:
   ```bash
   docker compose up -d --build
   ```
5. **Verify Health**:
   ```bash
   docker compose ps
   curl http://127.0.0.1:8080/api/health
   ```
6. **Reverse Proxy (Recommended)**: Place Nginx, Traefik, or Caddy with HTTPS and Basic Authentication
   in front of `127.0.0.1:8080` to securely access the Web Dashboard over the internet.
7. **Backups & maintenance**: Never copy, restore, or delete database files while the containers
   are running — Neo4j detects the change lazily and may panic days later. Always stop the service
   first (`docker compose stop neo4j`), do the file-level operation, then start it again. Back up
   the stopped volume to storage outside the host:
   ```bash
   docker compose stop neo4j
   docker run --rm -v tg-bot_neo4jdata:/data -v /srv/storage/backups:/backup alpine \
     tar czf /backup/neo4j-$(date +%F-%H%M).tar.gz -C /data .
   docker compose start neo4j
   ```

---

## Repository

- **GitHub**: [https://github.com/0resuto/tg-bot.git](https://github.com/0resuto/tg-bot.git)

---

## License

MIT — see [LICENSE](LICENSE).
