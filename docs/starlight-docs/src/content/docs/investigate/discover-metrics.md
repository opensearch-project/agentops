---
title: Discover Metrics
description: Discover, query, and visualize time-series metric data using PromQL in OpenSearch Dashboards
sidebar:
  order: 50
---

The **Metrics** page in OpenSearch Dashboards provides a dedicated interface for discovering, querying, and visualizing time-series metric data. It is optimized for working with Prometheus metrics using PromQL.

The page has two modes, switched with the radio toggle at the top:

- **Explore** — a no-code metric browser for finding metrics and filtering by labels.
- **Query** — a PromQL editor for authoring and visualizing expressions.

Both modes share the same time range picker and data source selector; switch at any time.

The **Metrics** page is available in Observability workspaces. To access it, navigate to an **Observability** workspace, then in the left navigation expand **Discover** and select **Metrics**.

## Explore mode

Browse and discover metrics without writing PromQL. Use it to find a metric when you don't yet know what to query.

![Metrics Explore mode showing metric browser with sparklines](https://github.com/opensearch-project/observability-stack/releases/download/v3.6.0-alpha.1/metrics-explore.webp)

The interface includes:

- A **metric browser** that lists all metrics from the data source as cards, each with a small sparkline preview.
- A **search box** with debounced server-side filtering by metric name.
- **Label filters** that narrow the metric list to only those carrying matching labels. Each filter row uses a Prometheus operator: `=`, `!=`, `=~` (regex match), or `!~` (regex not match).
- **Grouping** options that organize metric cards by **Prefix** (the namespace prefix of the metric name) or **A-Z** (alphabetical, in a single group).
- **Layout** options for **Grid** or **Rows**.
- **Metric type** badges — Counter, Gauge, Histogram, Summary, or Unknown — taken from Prometheus metric metadata, with a fallback that infers Counter and Histogram from name suffixes (`_total`, `_count`, `_sum`, `_created`, `_bucket`) when metadata is missing.

Click a metric card to open the **metric detail** view, which previews the time series broken down by label and lets you drill into a specific label combination. Or select one or more metric cards and select **Query Metrics** to send them into Query mode as a multi-query execution.

## Query mode

Author one or more PromQL expressions and render them in a chart. Use it when you know what you want to compute.

![Metrics Query mode with PromQL editor and visualization](https://github.com/opensearch-project/observability-stack/releases/download/v3.6.0-alpha.1/prometheus.webp)

Each query lives in its own row. A single execution can run several queries together — they're concatenated with semicolons (`;`) and rendered side by side on the visualization.

### Builder vs. Code

Each query row has two editor styles, toggled per row:

- **Builder** — a structured UI for selecting a metric, adding label filters with operators (`=`, `!=`, `=~`, `!~`), and chaining operations (aggregations, range functions, math). Useful when you're learning PromQL or want fewer typos.
- **Code** — a raw PromQL editor with autocomplete and syntax highlighting. Suggestions are fetched from the Prometheus data source and trigger on space, `(`, `{`, `[`, `,`, `=`, `~`, `'`, and `"`.

You can switch between Builder and Code at any time. Switching from Builder to Code reveals the underlying PromQL; the reverse parses your PromQL back into Builder controls when possible.

### Per-row query options

Each query row has a gear popover for options that apply to that row only:

- **Min step** — a lower bound on the resolved step, in seconds. It is also treated as the assumed scrape interval when sizing the `rate()` window.
- **Series name** — a `{{label}}` template that renames the returned series in the legend. For example, `{{job}} - {{instance}}` formats each series using the values of its `job` and `instance` labels.

Each row also displays the resolved step (`$__interval`) and rate window (`$__rate_interval`) it actually ran with.

### Interval macros

Queries can reference interval macros that are interpolated per query segment at execution time. Autocomplete suggests them in Code mode:

- `$__interval`, `$__interval_ms` — the resolved step, in seconds or milliseconds.
- `$__rate_interval` — the rate window sized for the resolved step and assumed scrape interval.
- `$__range`, `$__range_s`, `$__range_ms` — the active time range, as a duration string, seconds, or milliseconds.

For example, `rate(node_cpu_seconds_total[$__rate_interval])` sizes the rate window automatically as you zoom in and out.

### Writing queries

Write queries using PromQL syntax. For example:

```promql
up{job="prometheus"}
```

### Multiple queries in one execution

To run several queries together, add a row for each one (or, in Code mode, separate them with semicolons on different lines):

```promql
up{job="prometheus"};
node_cpu_seconds_total{mode="idle"};
```

Each query runs independently. The results are returned together and the visualization renders all series side by side.

### Step and resolution

The step is derived from the active time range, targeting a number of datapoints with a 15-second floor. The `rate()` window is sized to be at least four times the assumed scrape interval and at least one scrape interval larger than the step, so zoomed-out views don't show gaps.

In Query mode, a **Query options** popover on the panel exposes **Max data points**: the datapoint target the step is derived from (default 1440), shared across all query rows. Leave it blank to auto-resolve; the placeholder then reports the resolution used in the last run. Combine it with a row's **Min step** to control resolution precisely.

In Explore mode, sparkline and detail queries are generated using the same resolver, with a 60-second assumed scrape interval.

## Configuring a Prometheus data source

Before you start, configure a Prometheus data source using one of the following methods.

### Configuring a Prometheus data source in OpenSearch Dashboards

To configure a Prometheus data source in OpenSearch Dashboards, follow these steps:

1. In the left navigation, go to **Data Administration** > **Data sources**.
2. Select **Create data source**.
3. Select **Prometheus**.
4. Enter a **Data source name** and optional **Description**.
5. Enter the **Prometheus URI** endpoint (for example, `http://prometheus-server:9090`).
6. Configure the **Authentication method**:
   - **No authentication**: Use if your Prometheus server does not require authentication.
   - **Basic authentication**: Enter a username and password.
   - **AWS Signature Version 4**: Use for Amazon Managed Service for Prometheus.
7. Select **Connect**.

### Configuring a Prometheus data source using the API

Alternatively, you can configure a Prometheus data source programmatically. For more information, see the [Data sources documentation](https://docs.opensearch.org/latest/dashboards/management/data-sources/).

## Time filter

Use the time filter to specify the time range for your metric data:

- **Quick select**: Choose a relative time range (for example, the last 15 minutes or the last 1 hour).
- **Commonly used**: Select from predefined time ranges.
- **Custom**: Specify absolute start and end times.
- **Auto-refresh**: Set an automatic refresh interval.

## Viewing results

After running a query in **Query** mode, the results are displayed in a tabbed interface below the editor containing the following views:

- The **Visualization** tab provides interactive charts for your metric data.
- The **Table** tab displays each series as a row of latest values, with a banner if the response was truncated for performance.

### Series limit

To keep the browser responsive, the visualization renders up to **20 series** by default. If a query returns more, a banner appears with a **Show {count}** button to render all of them. Tighten label filters or aggregate (for example, `sum by (...)`) to bring the count down rather than rendering hundreds of series.

### Configuring visualizations

When the **Visualization** tab is selected, a settings panel appears on the right side of the screen. Use this panel to:

1. **Select a chart type**: Choose from line, bar, area, scatter, pie, heatmap, table, metric, gauge, bar gauge, state timeline, or histogram.
2. **Map axes**: Assign fields to the X and Y axes.
3. **Customize styles**: Adjust colors, legends, gridlines, thresholds, and units.

When you modify the settings, the visualization is updated automatically. See [Build a Dashboard](/docs/dashboards/build/) for details on each chart type and its options, and [Visualization transformations](/docs/dashboards/visualize/transformations/) for reshaping query results before they're charted.

## Saving and reusing

Metrics explorations are saved as **Explore** saved objects. Save a query from the page actions to revisit it later, or add a metrics view as a panel on a new or existing dashboard to track it alongside logs and traces. From the global **Visualize** application, choosing **Create visualization → Visualize with Metrics** also opens a fresh metrics canvas in Query mode.
