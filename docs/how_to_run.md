# How to Run InvestoBot - Complete Setup Guide

This guide provides step-by-step instructions for setting up and running InvestoBot, including database, backend, and frontend components.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Database Setup](#database-setup)
3. [Backend Setup](#backend-setup)
4. [Frontend Setup](#frontend-setup)
5. [Running the System](#running-the-system)
6. [Seed Data](#seed-data)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have the following installed:

- **Python 3.11+** - [Download Python](https://www.python.org/downloads/)
- **Node.js 22+** - [Download Node.js](https://nodejs.org/)
- **Supabase Account** - [Sign up for Supabase](https://supabase.com/) (free tier available)
- **Git** - [Download Git](https://git-scm.com/)

### Required API Keys

- **Google AI Studio API Key** - [Get API Key](https://aistudio.google.com/)
- **Alpaca Paper Trading Keys** (optional, for execution) - [Get Alpaca Keys](https://alpaca.markets/)

---

## Database Setup

### Step 1: Create Supabase Project

1. Go to [Supabase Dashboard](https://app.supabase.com/)
2. Click "New Project"
3. Fill in project details:
   - Name: `investobot` (or your preferred name)
   - Database Password: Choose a strong password (save it!)
   - Region: Choose closest to you
4. Wait for project to be created (2-3 minutes)

### Step 2: Get Database Credentials

1. In your Supabase project, go to **Settings** → **API**
2. Copy the following values:
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **anon/public key** (starts with `eyJ...`) - Used for frontend authentication
   - **service_role key** (keep this secret!) - **REQUIRED for backend database operations**

**Important**: The backend requires `SUPABASE_SERVICE_KEY` (service_role key) to write to the database. The service_role key bypasses Row Level Security (RLS), allowing the backend to perform all database operations without permission errors.

3. Go to **Settings** → **Database**
4. Copy the **Connection string** (under "Connection string" → "URI")
   - Format: `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`

### Step 3: Run Database Schema Migration

1. In Supabase Dashboard, go to **SQL Editor**
2. Click "New query"
3. **Run the unified schema** (recommended for new deployments):
   - Open `backend/migrations/004_unified_schema.sql`
   - Copy the entire contents and paste into the SQL editor
   - Click "Run" (or press Ctrl+Enter)
4. **Add timeframe support**:
   - Open `backend/migrations/005_add_timeframe_support.sql`
   - Copy the entire contents and paste into the SQL editor
   - Click "Run" (or press Ctrl+Enter)
5. **Configure Row Level Security (RLS) - Optional**:
   - **If using `SUPABASE_SERVICE_KEY` (recommended)**: You can skip this step. Service_role key bypasses RLS.
   - **If using `SUPABASE_KEY` (anon key)**: You must run RLS policies:
     - Open `backend/migrations/006_rls_policies.sql`
     - Copy the entire contents and paste into the SQL editor
     - Click "Run" (or press Ctrl+Enter)
     - This creates policies to allow anon role to perform database operations
6. Verify tables were created:
   - Go to **Table Editor** → You should see tables like:
     - Core tables: `strategy_runs`, `strategies`, `backtest_results`, `risk_assessments`, `execution_results`, `portfolio_snapshots`
     - Observability tables: `trades`, `risk_violations`, `fills`, `run_metrics`
     - Data management tables: `data_sources`, `data_metadata`, `data_quality_reports`
7. Verify `data_metadata` table has `timeframe` column:
   - Check that `data_metadata` table includes a `timeframe` column (default: '1d')

**Note**: The unified schema (`004_unified_schema.sql`) includes all previous migrations. For new deployments, use the unified schema instead of running individual migration files.

---

## Backend Setup

### Step 1: Navigate to Backend Directory

```bash
cd backend
```

### Step 2: Create Virtual Environment

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

If you encounter issues, try:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the `backend` directory:

```bash
# Copy example if it exists
cp .env.example .env

# Or create new file
touch .env  # Linux/Mac
# or
type nul > .env  # Windows
```

Edit `.env` with your credentials:

```env
# Google AI Studio
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_MODEL=gemini-2.0-flash
GOOGLE_PROJECT_ID=your_project_id
GOOGLE_LOCATION=global

# Supabase Database
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here  # REQUIRED for backend - bypasses RLS
SUPABASE_KEY=your_anon_key_here  # Optional - only needed if not using service_role key

# Alpaca Paper Trading (optional)
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets

# Data Source
DATA_SOURCE=synthetic  # or "yahoo" for real data
DATA_CACHE_ENABLED=true
DATA_CACHE_TTL_HOURS=24
DATA_QUALITY_CHECKS_ENABLED=true

# Application Settings
APP_ENV=dev
APP_DEBUG=false
ALLOW_EXECUTE=false  # Set to true only if you want to execute real orders
```

### Step 5: Verify Backend Setup

Test that the backend can start:

```bash
# From backend directory
python -m uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Press `Ctrl+C` to stop.

---

## Frontend Setup

### Step 1: Navigate to Frontend Directory

```bash
cd frontend
```

### Step 2: Install Dependencies

```bash
npm install
```

### Step 3: Configure Environment Variables

Create a `.env` file in the `frontend` directory:

```bash
# Copy example if it exists
cp .env.example .env

# Or create new file
touch .env  # Linux/Mac
```

Edit `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Step 4: Verify Frontend Setup

Test that the frontend can build:

```bash
npm run build
```

If successful, you should see a `dist` directory created.

---

## Running the System

### Option 1: Run Backend and Frontend Separately

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

The frontend will typically run on `http://localhost:5173` (Vite default).

### Option 2: Use npm Scripts (if configured)

From project root:
```bash
# Start backend
npm run start:backend

# Start frontend (in another terminal)
npm run start:frontend
```

### Verify System is Running

1. **Backend Health Check:**
   ```bash
   curl http://localhost:8000/health
   ```
   Should return: `{"status": "healthy"}`

2. **Frontend:**
   - Open browser to `http://localhost:5173`
   - You should see the InvestoBot dashboard

3. **Backend Status:**
   ```bash
   curl http://localhost:8000/status
   ```
   Should return environment info

---

## Seed Data

To populate the database with test data for development:

### Step 1: Ensure Backend is Set Up

Make sure you've completed backend setup and have Supabase credentials configured.

### Step 2: Run Seed Data Script

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python scripts/generate_seed_data.py
```

**Options:**
- `--clear`: Clear existing data before seeding (use with caution!)

**Example:**
```bash
python scripts/generate_seed_data.py --clear
```

### Step 3: Verify Seed Data

Check Supabase Table Editor:
- `strategy_runs` should have 5 runs
- `strategies` should have ~15 strategies
- `backtest_results`, `risk_assessments`, `execution_results` should have corresponding entries
- `portfolio_snapshots` should have snapshots
- `data_metadata` should have metadata entries

---

## Testing

### Backend Unit Tests

Run all tests:
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
PYTHONPATH=backend:. python -m pytest ../test/ -v
```

Run specific test file:
```bash
PYTHONPATH=backend:. python -m pytest ../test/test_data_manager.py -v
```

### API Integration Tests

Test API endpoints:
```bash
cd test
python test_api.py
```

Test specific endpoint:
```bash
python test_api.py --test health
python test_api.py --test data
python test_api.py --test strategy
```

### Frontend Tests (if configured)

```bash
cd frontend
npm test
```

---

## Troubleshooting

### Database Connection Issues

**Problem**: "Failed to connect to Supabase"

**Solutions**:
1. Verify `SUPABASE_URL` and `SUPABASE_KEY` in `.env` are correct
2. Check Supabase project is active (not paused)
3. Verify network connectivity
4. Check Supabase dashboard for any service issues

### Backend Won't Start

**Problem**: Import errors or module not found

**Solutions**:
1. Ensure virtual environment is activated
2. Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`
3. Check Python version: `python --version` (should be 3.11+)
4. Verify you're in the `backend` directory

**Problem**: Port 8000 already in use

**Solutions**:
1. Find and kill process using port 8000:
   ```bash
   # Linux/Mac
   lsof -ti:8000 | xargs kill
   
   # Windows
   netstat -ano | findstr :8000
   taskkill /PID <PID> /F
   ```
2. Or use a different port: `uvicorn app.main:app --port 8001`

### Frontend Build Errors

**Problem**: npm install fails

**Solutions**:
1. Clear npm cache: `npm cache clean --force`
2. Delete `node_modules` and `package-lock.json`, then reinstall
3. Check Node.js version: `node --version` (should be 22+)

**Problem**: Vite dev server won't start

**Solutions**:
1. Check if port 5173 is available
2. Try different port: `npm run dev -- --port 3000`
3. Clear Vite cache: `rm -rf node_modules/.vite`

### Data Loading Issues

**Problem**: "No data found" errors

**Solutions**:
1. Check `DATA_SOURCE` in `.env` (should be "synthetic" or "yahoo")
2. For Yahoo Finance: Ensure `yfinance` is installed: `pip install yfinance`
3. Check internet connection if using "yahoo" source
4. Verify date ranges are valid (not future dates)

### API Endpoint Errors

**Problem**: 500 Internal Server Error

**Solutions**:
1. Check backend logs for detailed error messages
2. Verify all environment variables are set correctly
3. Check database connection
4. Ensure all required tables exist in Supabase

**Problem**: CORS errors in browser

**Solutions**:
1. Verify backend CORS middleware is configured (should allow all origins in dev)
2. Check frontend `VITE_API_BASE_URL` matches backend URL
3. Ensure backend is running

### Seed Data Issues

**Problem**: Foreign key constraint errors

**Solutions**:
1. Run migrations in correct order (use unified schema: `004_unified_schema.sql` then `005_add_timeframe_support.sql`)
2. Don't use `--clear` if you have existing data with relationships
3. Check that `data_sources` table has default entries (should be created by unified schema)
4. Ensure `data_metadata` table has `timeframe` column (from migration 005)

---

## Next Steps

After setup is complete:

1. **Explore the Dashboard**: Open frontend and navigate through tabs
2. **Run a Strategy**: Use the "Run Strategy" tab to test the system
3. **View History**: Check "Strategy History" to see past runs
4. **Monitor Logs**: Check `backend/logs/` for application logs
5. **Review Documentation**: Read `docs/how it works.md` for system architecture

---

## Development Workflow

### Daily Development

1. **Start Backend:**
   ```bash
   cd backend
   source venv/bin/activate
   python -m uvicorn app.main:app --reload
   ```

2. **Start Frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Make Changes**: Edit code, backend will auto-reload, frontend will hot-reload

4. **Run Tests**: After making changes, run relevant tests

5. **Check Logs**: Monitor `backend/logs/` for application logs

### Database Changes

1. Create migration file in `backend/migrations/`
2. Run migration in Supabase SQL Editor
3. Update `db_models.py` if schema changed
4. Update seed data script if needed
5. Test with seed data

---

## Support

For issues or questions:
1. Check this guide first
2. Review `docs/how it works.md` for architecture details
3. Check GitHub issues (if repository is public)
4. Review application logs in `backend/logs/`

---

**Last Updated**: 2024-12-19

