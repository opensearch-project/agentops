# LangChain Bedrock Agent - OpenTelemetry Instrumentation Example

This example demonstrates how to instrument a LangChain agent application with OpenTelemetry to send telemetry data to the AgentOps observability stack using OTLP protocol.

## Features

- **LangChain Instrumentation**: Uses `opentelemetry-instrumentation-langchain` for automatic tracing
- **AWS Bedrock Integration**: Claude Sonnet 4 model with tool calling
- **OTLP Export**: Sends traces to AgentOps stack via gRPC
- **Gen-AI Semantic Conventions**: Captures LLM operations with standardized attributes
- **Tool Execution Tracing**: Automatic instrumentation of tool calls

## Architecture

```
User Query → LangChain Agent → AWS Bedrock (Claude)
                   ↓
              Tool Execution
                   ↓
  LangChainInstrumentor (Callback Handler)
                   ↓
             OpenTelemetry
                   ↓
          OTLP gRPC Exporter
                   ↓
        AgentOps Stack (localhost:4317)
```

## How It Works

The instrumentation works by:

1. **LangChainInstrumentor** wraps LangChain's `BaseCallbackManager.__init__`
2. Injects `OpenTelemetryLangChainCallbackHandler` into all LLM calls
3. Callback handler creates spans for LLM operations with Gen-AI attributes
4. Spans are batched and exported via OTLP to the AgentOps observability stack

## Telemetry Captured

### Spans Created

- **LLM Invocations** (`gen_ai.operation.name = "chat"`)
  - Provider: `gen_ai.provider.name = "aws_bedrock"`
  - Model: `gen_ai.request.model` and `gen_ai.response.model`
  - Token usage: `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens`
  - Request/response timing

- **Tool Calls**
  - Tool name and arguments
  - Tool execution results
  - Timing information

## Prerequisites

1. **AgentOps Stack Running**: Ensure the AgentOps observability stack is running
   ```bash
   cd ../../docker-compose
   docker compose up -d
   ```

2. **AWS Credentials**: Configure AWS credentials for Bedrock access
   ```bash
   aws configure
   # or set environment variables:
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_REGION=us-east-1
   ```

3. **Bedrock Model Access**: Ensure you have access to Claude Sonnet 4 in AWS Bedrock

## Setup

1. **Install dependencies** using uv:
   ```bash
   uv sync
   ```

   Or using pip:
   ```bash
   pip install -e .
   ```

## Run

Execute the example:

```bash
uv run main.py
```

Or with Python directly:

```bash
python main.py
```

## Expected Output

```
💰 LangChain Bedrock Financial Assistant 💰
============================================================

Setting up OpenTelemetry instrumentation...
✓ OpenTelemetry configured with LangChain instrumentation
  - Service: langchain-bedrock-agent v1.0.0
  - OTLP Endpoint: http://localhost:4317
  - Instrumentation: LangChain callback handler injected

📊 Telemetry enabled - all operations will be traced
   View traces at: http://localhost:5601
   (OpenSearch Dashboards)

📝 Query: If I invest $10,000 at 7% for 5 years, what will it be worth?

🔧 Tool calls made:
  - calculate_growth: {'initial_value': 10000.0, 'rate': 0.07, 'years': 5}
  → Result: $14,025.52

✅ Final Answer: $14,025.52

Cleaning up instrumentation...
✓ LangChain uninstrumented

============================================================
✅ Example complete!

View telemetry data:
  - Traces: http://localhost:5601 (OpenSearch Dashboards)
  - Metrics: http://localhost:9090 (Prometheus)

Telemetry includes:
  - LLM invocation spans with Gen-AI attributes
  - Token usage (input/output tokens)
  - Tool call information
  - Request/response timing
```

## View Telemetry

### OpenSearch Dashboards (Traces)

1. Open http://localhost:5601
2. Navigate to "Observability" → "Traces"
3. Search for service: `langchain-bedrock-agent`
4. View trace details including:
   - LLM invocation spans
   - Token usage metrics
   - Tool execution spans
   - Request/response timing

### Prometheus (Metrics)

1. Open http://localhost:9090
2. Query for metrics like:
   - `gen_ai_client_token_usage`
   - `gen_ai_client_operation_duration`

## Code Structure

- `main.py`: Main example with instrumentation setup
- `pyproject.toml`: Dependencies including OpenTelemetry packages
- `README.md`: This file

## Key Code Sections

### OpenTelemetry Setup

```python
from opentelemetry.instrumentation.langchain import LangChainInstrumentor

# Configure tracer provider and OTLP exporter
setup_telemetry(
    service_name="langchain-bedrock-agent",
    otlp_endpoint="http://localhost:4317"
)

# Instrument LangChain - injects callback handler
LangChainInstrumentor().instrument()
```

### Agent Creation

```python
# Create LangChain agent with Bedrock
llm = ChatBedrockConverse(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")
llm_with_tools = llm.bind_tools([calculate_growth])
agent = prompt | llm_with_tools

# Invoke agent - automatically traced
result = agent.invoke({"input": query})
```

### Cleanup

```python
# Uninstrument when done
LangChainInstrumentor().uninstrument()
```

## Troubleshooting

### No traces appearing

1. Check AgentOps stack is running: `docker-compose ps`
2. Verify OTLP collector is accessible: `curl http://localhost:4317`
3. Check for errors in console output

### AWS Bedrock errors

1. Verify AWS credentials: `aws sts get-caller-identity`
2. Check Bedrock model access in AWS console
3. Ensure correct region is configured

### Import errors

1. Reinstall dependencies: `uv sync` or `pip install -e .`
2. Check Python version: `python --version` (requires 3.12+)

## References

- [OpenTelemetry LangChain Instrumentation](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation/opentelemetry-instrumentation-langchain)
- [LangChain Documentation](https://python.langchain.com/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Gen-AI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
