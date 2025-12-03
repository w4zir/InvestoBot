# Render.com Deployment Guide

This guide explains how to deploy InvestoBot to Render.com with scheduled strategy runs.

## Overview

The deployment uses:
- **Web Service**: FastAPI application for API endpoints
- **Cron Jobs**: Scheduled strategy runs at market open/close

## Prerequisites

1. A Render.com account (free tier works for testing)
2. GitHub repository connected to Render
3. Environment variables configured (see below)

## Deployment Steps

### 1. Connect Repository

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Render will detect `render.yaml` and create services automatically

### 2. Configure Environment Variables

For each service (web service and cron jobs), set these environment variables in the Render dashboard:

**Required:**
- `GOOGLE_API_KEY`: Your Google AI Studio API key
- `GOOGLE_MODEL`: Model name (default: `gemini-2.0-flash`)

**Optional (for paper trading):**
- `ALPACA_API_KEY`: Alpaca paper trading API key
- `ALPACA_SECRET_KEY`: Alpaca paper trading secret key
- `ALPACA_PAPER_BASE_URL`: `https://paper-api.alpaca.markets`

**Optional (for data):**
- `DATA_SOURCE`: `synthetic` or `yahoo` (default: `synthetic`)
- `APP_ENV`: `production` or `dev` (default: `dev`)

**For Cron Jobs:**
- `SCHEDULED_MISSION`: Mission statement for the strategy run
- `SCHEDULED_UNIVERSE`: Comma-separated symbols (e.g., `AAPL,MSFT,GOOGL`)
- `SCHEDULED_EXECUTE`: `true` or `false` (default: `false`)

### 3. Adjust Cron Schedule

The `render.yaml` file includes cron schedules in UTC. Adjust for your timezone:

**Market Open (9:30 AM ET):**
- Standard Time (EST): `30 14 * * 1-5` (2:30 PM UTC)
- Daylight Time (EDT): `30 13 * * 1-5` (1:30 PM UTC)

**Market Close (4:00 PM ET):**
- Standard Time (EST): `0 21 * * 1-5` (9:00 PM UTC)
- Daylight Time (EDT): `0 20 * * 1-5` (8:00 PM UTC)

Update the `schedule` field in `render.yaml` or in the Render dashboard.

### 4. Deploy

1. Render will automatically build and deploy when you push to your repository
2. Or manually trigger a deploy from the Render dashboard
3. Check logs to ensure services start correctly

## API Endpoints

Once deployed, your API will be available at:
- `https://your-service-name.onrender.com`

**Key Endpoints:**
- `POST /strategies/run` - Run a strategy manually
- `GET /control/kill-switch/status` - Check kill switch status
- `POST /control/kill-switch/enable` - Enable kill switch
- `POST /control/kill-switch/disable` - Disable kill switch
- `POST /control/orders/cancel-all` - Cancel all open orders
- `GET /control/orders/open` - List open orders
- `GET /control/scheduler/status` - Check scheduler status

## Kill Switch Usage

The kill switch prevents all strategy executions:

```bash
# Enable kill switch
curl -X POST https://your-service.onrender.com/control/kill-switch/enable?reason="Emergency stop"

# Check status
curl https://your-service.onrender.com/control/kill-switch/status

# Disable kill switch
curl -X POST https://your-service.onrender.com/control/kill-switch/disable
```

## Monitoring

1. **Logs**: View logs in Render dashboard for each service
2. **Cron Jobs**: Check cron job logs to see scheduled run results
3. **API Health**: Use `/health/` endpoint to check service status

## Troubleshooting

### Cron Jobs Not Running

1. Check cron job logs in Render dashboard
2. Verify environment variables are set
3. Ensure `SCHEDULED_MISSION` is configured
4. Check that kill switch is not enabled

### Kill Switch Blocking Runs

```bash
# Check status
curl https://your-service.onrender.com/control/kill-switch/status

# Disable if needed
curl -X POST https://your-service.onrender.com/control/kill-switch/disable
```

### Timezone Issues

- Render cron jobs run in UTC
- Adjust schedules in `render.yaml` or Render dashboard
- Use `is_market_open()` function in code to check market hours

## Cost Considerations

- **Free Tier**: Limited hours per month, services sleep after inactivity
- **Starter Plan**: $7/month per service, always-on
- **Cron Jobs**: Free tier includes 750 hours/month

For production, consider:
- Starter plan for web service (always-on)
- Free tier for cron jobs (runs only when scheduled)

## Security Notes

1. Never commit API keys to repository
2. Use Render's environment variable encryption
3. Keep `SCHEDULED_EXECUTE=false` until ready for paper trading
4. Monitor logs for unauthorized access
5. Use kill switch in emergencies

## Next Steps

1. Test with `SCHEDULED_EXECUTE=false` first
2. Monitor cron job logs for a few days
3. Enable execution only after thorough testing
4. Set up alerts for kill switch activations
5. Consider adding webhook notifications for run completions

