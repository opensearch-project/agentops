---
title: Anomaly Detection
description: Detect anomalies in your observability data using machine learning
---

OpenSearch Anomaly Detection uses machine learning to automatically identify unusual patterns in your time-series data. It learns the normal behavior of your metrics and alerts you when something deviates from the expected pattern - without requiring manual threshold configuration.

## Key concepts

- **Detector**: A configuration that defines what data to monitor, which features (aggregations) to track, and how often to check. Each detector uses the Random Cut Forest (RCF) algorithm to model normal behavior.
- **Features**: The aggregations a detector monitors - for example, average CPU usage, request count, or error rate over a time window.
- **Real-time detection**: The detector runs continuously and flags anomalies as new data arrives. Results are available within the detection interval (typically 1-10 minutes).
- **Historical detection**: Run a detector against past data to identify anomalies retroactively. Useful for validating detector configuration or investigating past incidents.
- **Anomaly grade**: A score from 0 to 1 indicating how severe the anomaly is. Higher grades mean the data point is further from expected behavior.
- **Confidence**: How certain the model is in its prediction. Confidence increases as the detector processes more data.

## How it fits the Observability Stack

Anomaly detection works on any time-series data indexed in OpenSearch. Common observability use cases:

| Use case | Feature to monitor |
|---|---|
| Latency spikes | Average or P95 request duration from trace data |
| Error surges | Count of error-level log entries |
| Traffic anomalies | Request rate from service metrics |
| Resource exhaustion | CPU or memory usage from infrastructure metrics |

## Getting started

1. Open OpenSearch Dashboards and navigate to **Anomaly Detection** (under the main menu).
2. Click **Create detector**.
3. Select the index to monitor (e.g., `logs-otel-v1*` or a metrics index).
4. Define one or more **features** - aggregations over fields in your data.
5. Set the **detection interval** (how often the detector evaluates).
6. Optionally configure a **category field** to run detection per group (e.g., per service name).
7. Start the detector in real-time mode.
8. View results on the detector's dashboard - anomaly grade, confidence, and feature values over time.

## Pairing with alerting

Combine anomaly detection with [Alerting](/docs/alerting/) to get notified when anomalies are detected. Create a [log rule](/docs/alerting/unified-alerts/create-rules/#log-rule-ppl) that queries the anomaly results index and fires when the anomaly grade exceeds a threshold — for example:

```
source=.opendistro-anomaly-results* | where anomaly_grade > 0.7 | stats count() as anomalies
```
```
where anomalies > 0
```

Detectors also appear in the **Rules** catalog of the [Unified Alerts View](/docs/alerting/unified-alerts/), so their alerts surface alongside your log and metric rules.

## Learn more

For the full reference - including detector APIs, tuning parameters, and multi-category detection - see the [Anomaly Detection documentation](https://docs.opensearch.org/latest/observing-your-data/ad/index/) in the official OpenSearch docs.
