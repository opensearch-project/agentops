# Canary Service

The canary service is a periodic test client that invokes the weather-agent API to generate continuous telemetry data for testing and demonstration purposes.

## Purpose

- Validates the observability pipeline end-to-end
- Generates synthetic agent traffic for testing
- Provides continuous telemetry data for demonstrations
- Monitors weather-agent availability and success rate

## Files

- `canary.py`: Main canary implementation
- `Dockerfile`: Container build configuration

## Configuration

Environment variables (set in `../.env`):

- `CANARY_INTERVAL`: Seconds between invocations (default: 30)
- `CANARY_MEMORY_LIMIT`: Memory limit for the container (default: 100M)
- `WEATHER_AGENT_URL`: URL of the weather-agent (automatically set to `http://weather-agent:8000`)

## Usage

The canary service is part of the `examples` profile and starts automatically when you run:

```bash
finch compose --profile examples up -d
```

View canary logs:
```bash
finch compose logs -f canary
```

## How It Works

1. **Startup**: Waits for weather-agent to become healthy (up to 60 seconds)
2. **Main Loop**: 
   - Randomly selects a weather query
   - Invokes the weather-agent API
   - Logs the response and success rate
   - Waits for the configured interval
   - Repeats

## Sample Queries

The canary randomly selects from these queries:
- "What's the weather in Paris?"
- "How's the weather in Tokyo?"
- "Tell me the weather in New York"
- "What's the weather like in London?"
- "Is it raining in Seattle?"
- "What's the temperature in Berlin?"
- "How's the weather in Sydney?"
- "What's the weather in Mumbai?"

## Modifying

After editing `canary.py`, rebuild and restart:

```bash
finch compose build --no-cache canary
finch compose restart canary
```

## Troubleshooting

If the canary fails to connect:
1. Check weather-agent health: `curl http://localhost:8000/health`
2. View canary logs: `finch compose logs canary`
3. Verify both services are on the same network: `finch compose ps`
