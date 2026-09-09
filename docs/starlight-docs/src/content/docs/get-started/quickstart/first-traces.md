---
title: Ingest Your First Traces
description: Instrument your application to send traces to the Observability Stack
---

## 1. Install dependencies

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

:::tip[OpenTelemetry auto-instrumentation]
The example below instruments a span by hand so you can see what a trace is made
of. For a real service, [auto-instrumentation](/docs/send-data/opentelemetry/auto-instrumentation/)
is usually the faster path: it emits HTTP, database and framework spans with no
code changes, and is available for Python, Java, Node.js, Go, .NET and Ruby.
:::

## 2. Send traces

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("my-app")

with tracer.start_as_current_span("handle-request") as span:
    span.set_attribute("http.method", "GET")
    span.set_attribute("http.url", "/api/users")

    with tracer.start_as_current_span("query-database") as child:
        child.set_attribute("db.system", "postgresql")
        # your database query here
```

For other languages, see [Send Data](/docs/send-data/).

## 3. View traces in OpenSearch Dashboards

1. Open [OpenSearch Dashboards](http://localhost:5601)
2. Navigate to **Observability** → **Traces**
3. Search for your trace by name or filter by time range
4. Click a trace to see the span tree, timing, and attributes

## Next steps

- [Create Your First Dashboard](/docs/get-started/quickstart/first-dashboard/) - build custom visualizations
- [Agent Tracing](/docs/ai-observability/agent-tracing/) - trace AI agent workflows with GenAI semantic conventions
- [Application Monitoring](/docs/apm/) - service maps and RED metrics built from the traces you just sent
- [Send Data](/docs/send-data/) - more instrumentation options
