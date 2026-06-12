# LY Distilled Node

Serverless heartbeat agent for LY-TRINITY distributed network.

## Deploy

Deploy to Vercel with environment variables:

- `LY_HB_URL`: Supabase REST endpoint for heartbeats
- `LY_HB_KEY`: Supabase service_role key
- `LY_NODE_ID`: Unique node identifier

## API Routes

- `GET /api/heartbeat` - Trigger heartbeat
- `POST /api/execute` - Execute task
