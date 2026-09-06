# Flight Disruption Assistant — `app` Package

This is the distributable agent package for the **Flight Disruption Assistant**, officially registered in the **AA AI Engineering Agent Registry** on the **AA AI Engineering Marketplace**.

The assistant operates in the airline domain during irregular operations (IROPS):

- **Passenger rebooking** — offers alternative flights when a leg is cancelled or delayed
- **Baggage tracing** — tracks delayed or mishandled baggage through the handling pipeline
- **Disruption notifications** — proactively notifies passengers across email, SMS, and push channels

## Distribution via Agent Registry

This agent is distributed exclusively through the Agent Registry. When you download this agent from the AI Marketplace, you receive only this `app` folder — the self-contained agent implementation. This distribution model ensures:

- **Standardized delivery** — all agents shared via the marketplace follow the same folder-based packaging contract
- **Lightweight and portable** — no build tooling, no scaffolding, no environment boilerplate included
- **Secure provenance** — downloads are served directly through the Agent Registry, giving every agent a single source of truth

## Using with the Runway AI Template

This `app` folder is designed to drop directly into the Runway AI Template. To instantiate the Flight Disruption Assistant:

1. Download this agent from the AI Marketplace
2. Replace the `app` folder in your Runway AI Template project with this one
3. Add the packages listed in [Additional Dependencies](#additional-dependencies) to the `[packages]` section of the template's `Pipfile`
4. Create a `.env` file at the project root and populate it with the required variables (see [Configuration](#configuration) below)
5. Run `pipenv install && pipenv run start`

The Runway AI Template provides the outer runtime harness (Pipfile, Dockerfile, Kubernetes manifests); this folder provides the agent logic.

### Verify the Setup

Once running, confirm the service is healthy:

```bash
# Health check — returns service metadata (name, version, environment, capabilities)
curl http://localhost:8000/api/v1/status
```

Interactive API docs are available at `http://localhost:8000/docs`.

## What Is in This Folder

```
app/
├── main.py                        # FastAPI application entry point
├── config.py                      # Pydantic settings (AppSettings, AgentSettings)
├── core/
│   └── otel_logger.py             # Structured structlog logging
├── status/                        # GET /api/v1/status health + metadata endpoint
│   ├── models/
│   │   └── models.py              # Status response Pydantic model
│   ├── routers/
│   │   └── status_router.py       # /status route
│   └── services/
│       └── status_service.py      # StatusService — builds the metadata response
└── requirements.txt               # Python dependencies for standalone installs
```

## Additional Dependencies

The following packages are required by this agent but are **not included** in the Runway AI Template's `Pipfile`. Add them to the `[packages]` section before running `pipenv install`.

| Package | Version | Purpose |
|---|---|---|
| `structlog` | `==25.5.0` | Structured JSON logging used by the service harness |

All other runtime packages used by this agent (`fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`) are already present in the Runway AI Template.

## Configuration

Create a `.env` file at the project root and set the following variables:

```bash
# APIM or Foundry (required by the full IROPS rebooking pipeline; not used by the status harness)
AZURE_APIM_ENDPOINT=https://your-apim.azure-api.net/testapi/openai/
AZURE_APIM_SUBSCRIPTION_KEY=your-key
AZURE_OPENAI_MODEL=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Service metadata (optional overrides)
APP_TITLE=aiep-agent-flight-disruption
APP_VERSION=1.0.0
ENV=local
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# Disruption handling tuning (defaults shown)
MAX_REBOOKING_OPTIONS=5
NOTIFICATION_RETRY_COUNT=3
HITL_REQUIRED=true
```

## Agent Registry

This agent is registered in the AA AI Engineering Agent Registry. Registry metadata — including version history, I/O schemas, SLA tier, and capability tags — is managed through the marketplace.

| Field | Value |
|---|---|
| Registry | AA AI Engineering Agent Registry |
| Marketplace route | `/agents` |
| Status | Draft |
| Distribution | `app` folder download |

---

**Built for American Airlines by the AIEP Team**
