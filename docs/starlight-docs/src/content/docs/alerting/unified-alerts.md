---
title: Unified Alerts View
description: One list for OpenSearch monitors and Prometheus alerts, with rules and routing in the same app
---

The **Unified Alerts View** (labeled **Alerts** in the OpenSearch Dashboards side navigation, and **Alert Manager** in the menu) brings every alert in the stack into a single screen. Whether an alert came from an OpenSearch Alerting monitor or from a Prometheus rule, responders see it in one list, filter it the same way, and never have to know which engine produced it.

![Walkthrough of the Unified Alerts view cycling through the Alerts, Rules, and Routing tabs with both datasources selected](/docs/images/alerting/unified-alerts-walkthrough.gif)

*Cycling through the **Alerts**, **Rules**, and **Routing** tabs with both datasources selected. SLO burn-rate alerts appear in the same queue.*

## Layout

The view has three tabs:

| Tab | What it shows |
|---|---|
| **Alerts** | Every currently firing (and, where available, historical) alert across the selected datasources. |
| **Rules** | Every alerting rule / monitor definition, with status, severity, type, and health. |
| **Routing** | The alert manager routing tree — which receiver each alert is sent to. |

### Filters

The left rail scopes the list without editing any query:

- **Datasource** — pick the OpenSearch cluster (its monitors), the Prometheus datasource (its alerts), or both.
- **Severity** — `critical`, `medium`, and so on, with live counts.
- **State** — `active`, `pending`, `resolved`.
- **Labels** — every label present on the current alert set (`alertname`, `component`, `service`, `job`, …) becomes a facet. This is where Prometheus label cardinality pays off: filter to one service, one exporter, or one component in a click.

### Alert timeline

The histogram at the top of the **Alerts** tab buckets firing alerts over the selected time range (default **Last 24 hours**), colored by severity. Use it to spot bursts — a spike of `critical` bars usually lines up with an incident.

### Rules tab

The **Rules** tab lists every rule/monitor from both engines side by side, with status, severity, type, health, and the owning datasource. Filter by any of those facets.

### Routing tab

The **Routing** tab is a read-only view of the alert manager route tree: which receiver gets which alerts, the grouping and timing settings, and the configured receivers (webhook, Slack, email, PagerDuty). Routing is managed in the alert manager's own configuration.

## Selecting datasources

By default only the OpenSearch cluster is selected. To see Prometheus alerts, tick the **Prometheus datasource** in the **Datasource** filter. The tab counts update immediately to reflect both engines. Because [SLOs](/docs/slo/) deploy their burn-rate alerts as Prometheus rules, SLO breaches appear in this list too — the unified queue is where they surface.

:::note[Prometheus shows current alerts only]
Prometheus does not retain historical alert instances the way OpenSearch does. When the Prometheus datasource is selected you'll see a `Showing current alerts only` banner — the list reflects what is firing *right now*, evaluated every minute, rather than a historical record.
:::

## Empty tabs

If the **Alerts** and **Rules** tabs are empty, there are no monitors or rules for the selected datasources yet, or nothing is currently firing. Confirm the right datasources are selected in the filter, create a monitor or rule, or generate some load so alerts have something to fire on.

## Related

- [Alerting](/docs/alerting/) — the two alerting surfaces and how they route.
- [SLOs](/docs/slo/) — SLO burn-rate and error-budget alerts surface here too.
