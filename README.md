# InvestoBot – FastAPI Orchestrator + React Frontend

InvestoBot is an autonomous trading bot MVP built on a FastAPI backend and a React (TypeScript) frontend.  
The backend acts as an orchestrator that uses Google AI Agents to plan strategies, runs deterministic backtests, applies a risk engine, and optionally executes trades via the Alpaca paper trading API. The frontend is a Supabase-authenticated dashboard that can later be extended to visualize metrics and runs.

## Tech Stack

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **TailwindCSS** for styling
- **shadcn/ui** for UI components
- **React Router** for navigation
- **Framer Motion** for animations
- **Supabase Client** for authentication
- **Lucide React** for icons

### Backend
- **FastAPI** (Python 3.11+)
- **Uvicorn** ASGI server
- **Pydantic** for data validation
- **Google GenAI / Agents SDK** (`google-genai`) for strategy-planning agents
- **Alpaca Paper Trading API** (via HTTP client)

### Development Tools
- **uv** for Python virtual environment and package management
- **concurrently** for running frontend and backend simultaneously
- **Node.js 22** (managed via nvm)

## Prerequisites

- Node.js 22+ (recommended: use [nvm](https://github.com/nvm-sh/nvm))
- Python 3.11+ (recommended: use [pyenv](https://github.com/pyenv/pyenv))
- [uv](https://github.com/astral-sh/uv) for Python package management
- A Supabase project ([create one here](https://supabase.com))

## Quick Start

### 1. Clone and Install Dependencies

```bash
# Install Node.js dependencies
npm install

# Setup backend (creates virtual environment and installs Python packages)
npm run setup:backend
```

### 2. Configure Environment Variables

Create environment files (these are gitignored and won't be committed).

**Root `.env` file** (for backend):

```bash
# Optional: Supabase Configuration (if you use Supabase from backend)
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_KEY=your_supabase_service_role_key

# Google AI Agents / GenAI
GOOGLE_API_KEY=your_google_api_key
GOOGLE_MODEL=gemini-2.0-flash
# Optional, if you later create a dedicated agent
GOOGLE_AGENT_ID=your_agent_id

# Alpaca Paper Trading
ALPACA_API_KEY=your_alpaca_paper_key
ALPACA_SECRET_KEY=your_alpaca_paper_secret
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets

# Risk and data configuration (optional overrides)
APP_ENV=dev
APP_DEBUG=false
```

**`frontend/.env` file** (for frontend Supabase auth):

```bash
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

### 3. Run the Application

```bash
# Run both frontend and backend simultaneously
npm run dev:both
```

Or run them separately:

```bash
# Terminal 1: Backend (runs on http://localhost:8000)
npm run backend

# Terminal 2: Frontend (runs on http://localhost:5173)
npm run frontend
```

### 4. Access the Application

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health/
- Strategy run endpoint: `POST http://localhost:8000/strategies/run`
- Trading status endpoint: `GET http://localhost:8000/trading/account`

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py          # Centralized app, risk, Alpaca, Google settings
│   │   │   ├── database.py        # (Optional) Supabase database client
│   │   │   └── logging.py         # Logging configuration helpers
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── google_client.py   # Google GenAI / Agents client wrapper
│   │   │   └── strategy_planner.py# Calls agent and returns StrategySpec models
│   │   ├── trading/
│   │   │   ├── __init__.py
│   │   │   ├── models.py          # Strategy, backtest, risk, order models
│   │   │   ├── market_data.py     # OHLCV data loading (synthetic placeholder)
│   │   │   ├── backtester.py      # Deterministic backtest (placeholder)
│   │   │   ├── risk_engine.py     # Risk checks on proposed trades
│   │   │   ├── broker_alpaca.py   # Alpaca paper-trading adapter
│   │   │   └── orchestrator.py    # High-level run_strategy orchestration
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py          # Health check endpoint
│   │   │   ├── strategies.py      # /strategies/run endpoint
│   │   │   └── status.py          # /trading/account endpoint
│   │   └── main.py                # FastAPI application entrypoint
│   └── requirements.txt           # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── supabase.ts        # Supabase client configuration
│   │   ├── components/
│   │   │   ├── ui/                # shadcn/ui components
│   │   │   └── Navbar.tsx         # Navigation component
│   │   ├── pages/
│   │   │   ├── Login.tsx          # Authentication page
│   │   │   ├── Dashboard.tsx      # Protected dashboard
│   │   │   └── NotFound.tsx       # 404 page
│   │   ├── App.tsx                # Main app component with routing
│   │   └── main.tsx               # Entry point
│   └── package.json
├── scripts/
│   ├── run-backend.js             # Backend runner script
│   └── setup-backend.js           # Backend setup script
└── README.md
```

## Backend Architecture

At a high level, the backend implements the following flow:

1. **Strategy planning (LLM / Google Agent)**  
   The `agents.strategy_planner` module uses Google GenAI (`google-genai`) to propose candidate strategy specs (`StrategySpec`) based on a mission and context.

2. **Backtesting**  
   The `trading.backtester` module runs a deterministic (currently placeholder) backtest over OHLCV data from `trading.market_data`, producing metrics such as Sharpe ratio and max drawdown.

3. **Risk engine**  
   The `trading.risk_engine` module enforces simple, deterministic rules such as per-trade notional limits and symbol blacklists.

4. **Execution (optional)**  
   If enabled in the request context, the orchestrator uses `trading.broker_alpaca` to send approved orders to the Alpaca paper trading API.

5. **API surface**  
   - `POST /strategies/run` – trigger the full pipeline (plan → backtest → risk → optional execute).  
   - `GET /trading/account` – view Alpaca account + positions snapshot.  
   - `GET /health/` – basic health check.

This design keeps the core trading logic server-side and ready for future integration with the React dashboard or other clients.

## Features

### Authentication
- Email/password sign up and login
- Google OAuth authentication
- Password reset functionality
- Protected routes with automatic redirects
- Session management via Supabase Auth

### UI Components
- Pre-configured shadcn/ui components
- Responsive design with TailwindCSS
- Dark mode support (via shadcn/ui)
- Smooth animations with Framer Motion

### Backend
- FastAPI with automatic API documentation
- CORS configured for development
- Health check endpoint
- Minimal database client setup

## Available Scripts

### Frontend
- `npm run dev` - Start Vite dev server
- `npm run build` - Build for production
- `npm run preview` - Preview production build

### Backend
- `npm run setup:backend` - Setup Python virtual environment and install dependencies
- `npm run backend` - Run FastAPI server with hot reload

### Both
- `npm run dev:both` - Run both frontend and backend simultaneously

## Development

### Adding New Routes (Backend)

1. Create a new file in `backend/app/routes/`:
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/example")
async def example():
    return {"message": "Hello World"}
```

2. Include it in `backend/app/main.py`:
```python
from .routes import example

app.include_router(example.router, prefix="/example", tags=["Example"])
```

### Adding New Pages (Frontend)

1. Create a new component in `frontend/src/pages/`
2. Add route in `frontend/src/App.tsx`:
```tsx
import NewPage from './pages/NewPage'

<Route path="/new-page" element={<NewPage />} />
```

### Using Supabase in Backend

```python
from app.core.database import db

# Access Supabase client
if db.client:
    response = db.client.table("your_table").select("*").execute()
    data = response.data
```

### Using Supabase in Frontend

```typescript
import { supabase } from './api/supabase'

// Query data
const { data, error } = await supabase
  .from('your_table')
  .select('*')
```

## Customization

### Change App Name
- Update `frontend/src/components/Navbar.tsx` - change "App" to your app name
- Update `frontend/src/pages/Login.tsx` - change "Welcome" title

### Add Environment Variables
- Backend: Add to `.env` in project root, access via `os.getenv()`
- Frontend: Add to `.env` in `frontend/` directory, prefix with `VITE_`, access via `import.meta.env.VITE_YOUR_VAR`

### Styling
- TailwindCSS config: `frontend/tailwind.config.ts`
- Global styles: `frontend/src/styles/index.css`
- Component styles: Use Tailwind classes or CSS modules

## Deployment

### Frontend (Vercel/Netlify)
1. Build: `npm run build`
2. Deploy the `frontend/dist` directory
3. Set environment variables in your hosting platform

### Backend (Railway/Render/Fly.io)
1. Ensure `requirements.txt` is up to date
2. Set environment variables
3. Deploy with Python 3.11+ runtime
4. Run: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Troubleshooting

### Backend Issues
- **Virtual environment not found**: Run `npm run setup:backend`
- **Import errors**: Ensure you're in the `backend/` directory or using the venv Python
- **Supabase connection fails**: Check `.env` file has correct `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`

### Frontend Issues
- **Supabase auth not working**: Verify `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `frontend/.env`
- **Build errors**: Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- **Port already in use**: Change port in `frontend/vite.config.ts` or kill the process using the port

## License

MIT

## Contributing

This is a starter template. Feel free to fork and customize for your needs!
