# FastAPI + React Starter Template

A modern, production-ready starter template for building full-stack web applications with FastAPI (Python) backend and React (TypeScript) frontend, featuring Supabase authentication.

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
- **Supabase Python Client** for database operations
- **Pydantic** for data validation

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

Create environment files (these are gitignored and won't be committed):

**Root `.env` file** (for backend):
```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
```

**`frontend/.env` file** (for frontend):
```bash
# Supabase Configuration
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

**Where to find Supabase keys:**
- Go to your Supabase project dashboard
- Navigate to Settings → API
- Copy the `URL` and `anon` key for frontend
- Copy the `service_role` key for backend (keep this secret!)

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

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   └── database.py      # Supabase database client
│   │   ├── routes/
│   │   │   └── health.py         # Health check endpoint
│   │   └── main.py               # FastAPI application
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── supabase.ts       # Supabase client configuration
│   │   ├── components/
│   │   │   ├── ui/               # shadcn/ui components
│   │   │   └── Navbar.tsx        # Navigation component
│   │   ├── pages/
│   │   │   ├── Login.tsx         # Authentication page
│   │   │   ├── Dashboard.tsx     # Protected dashboard
│   │   │   └── NotFound.tsx      # 404 page
│   │   ├── App.tsx               # Main app component with routing
│   │   └── main.tsx              # Entry point
│   └── package.json
├── scripts/
│   ├── run-backend.js            # Backend runner script
│   └── setup-backend.js          # Backend setup script
└── README.md
```

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
