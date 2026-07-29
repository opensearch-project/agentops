---
title: "PPL Query Builder"
description: "Build PPL queries by pointing and clicking: search, filter, aggregate, and sort logs from menus, with a Code mode escape hatch."
---

The **PPL Query Builder** gives you a visual editing surface for PPL on the [Discover Logs](/docs/investigate/discover-logs/) page. You pick fields and values from menus, and the builder compiles the PPL.

It covers a subset of PPL: search, filter, aggregate, and sort. For anything outside that subset, switch to **Code** mode and write the PPL by hand.

![PPL Query Builder on the Logs page, with a Where filter, a Count aggregation, an hourly time bucket, and the aggregation menu open](/docs/images/ppl/ppl-query-builder.png)

:::note[Availability]
The query builder ships in OpenSearch Dashboards 3.8.0, switched off by default. Set `explore.logsQueryBuilder.enabled: true` in `opensearch_dashboards.yml` to turn it on. See [Enabling the builder](#enabling-the-builder).
:::

## Builder mode and Code mode

You edit a logs query in one of two modes. The **Code** / **Builder** toggle at the upper right of the query panel switches between them.

| Mode | Description |
|------|-------------|
| **Builder** | The visual surface: a search box plus **Where**, **Aggregations**, **Group by**, and **Sort by** controls. |
| **Code** | The raw PPL editor, with syntax highlighting and autocomplete. Handles anything the builder cannot represent. |

A new logs query opens in Builder mode. A query loaded from a saved search opens in Code mode, and you can switch to Builder from there.

### Switching between modes

A query you build in Builder mode moves freely between the two modes. Switch **Builder → Code** and the editor opens with the PPL the builder generated, so you can build a query by clicking and then read the PPL behind it. Switch back and your builder controls return as they were.

Once you write or edit PPL in Code mode, the query stays in Code. **Builder** greys out, and its tooltip reads *"This query cannot be represented in Builder mode. Simplify it or use Code mode."*

Clear the query bar to start fresh in Builder.

## Searching

The **Search for** box at the top of the builder edits the PPL `search` expression. A dedicated search-expression grammar drives its autocomplete, so it offers what parses at your cursor:

- **Field names** from the current dataset. Accepting one inserts `field=` and re-opens the suggestion list.
- **Live field values** for the field you named, pulled from the index.
- **Operators** `=`, `!=`, `>`, `>=`, `<`, `<=`.
- **Keywords** `AND`, `OR`, `NOT`, and `IN`.

Two conditions side by side with no operator between them combine with `AND`. Precedence follows PPL: parentheses bind tightest, then `NOT`, then `OR`, then `AND`. This differs from SQL. See [`search`](/docs/ppl/commands/search/) for the details.

## Filtering with Where

The **Where** row holds filter chips, and each chip compiles to one `where` command. Select **Where** to add a chip, then pick a field, an operator, and one or more values. The value menu lists live values from the index, so you filter on values you can see.

The field's mapped type determines which operators you get:

| Operator | Applies to | Compiles to |
|----------|-----------|-------------|
| **is** | any field | `` `field` = value `` |
| **is not** | any field | `` `field` != value `` |
| **is one of** | string, number, date, ip, geo | `` `field` = a OR `field` = b `` |
| **is not one of** | string, number, date, ip, geo | `` `field` != a AND `field` != b `` |
| **is between** | number, date, ip | `` `field` >= from AND `field` < to `` |
| **is not between** | number, date, ip | `` `field` < from OR `field` >= to `` |
| **exists** | any field | `` ISNOTNULL(`field`) `` |
| **does not exist** | any field | `` ISNULL(`field`) `` |

Ranges are half-open: `from` is inclusive, `to` is exclusive. Fill in one side and the chip emits that single comparison.

Hover a chip to see the predicate it emits. A chip with a field but no value yet contributes nothing to the query and shows *"Finish this condition"*.

## Aggregating

Select **Aggregation** to add a metric, then **Group by** to bucket it. Together they compile to a single `stats` command.

Metrics cover `count`, `sum`, `avg`, `min`, `max`, `median`, `percentile`, `distinct_count`, and the standard deviation and variance pairs. Each one that takes a field also offers a **Wrap in function** menu of math, string, and date functions to apply before aggregating.

Group by one or more fields, and add **Over time** for a `span()` time bucket on the dataset's time field. The builder sizes that interval to your current time range, and you can override it.

## Sorting

The **Sort** control adds a single `sort` command with a **Desc** or **Asc** direction. On a plain query you sort on any field; once the query aggregates, you sort on a column it emits, either a metric such as `count()` or one of the group-by fields.

## Running the query

Select **Refresh**, or press `Cmd`/`Ctrl` + `Enter` from anywhere in the builder.

Your edits do not run the query as you type. The builder holds the generated query as a draft until you run it, so the results table and histogram keep showing the last query you ran.

## Worked example

This builder configuration:

- **Search for**: `` `resource.attributes.service.name`=frontend-proxy ``
- **Where**: `attributes.http.response.status_code` **is between** `500` and `600`
- **Aggregations**: `Count`
- **Group by**: `attributes.url.path`, over time every `1m`
- **Sort by**: `count()`, `Desc`

generates:

```sql
`resource.attributes.service.name`=frontend-proxy
| WHERE `attributes.http.response.status_code` >= 500 AND `attributes.http.response.status_code` < 600
| stats count() by `attributes.url.path`, span(time, 1m)
| sort -`count()`
```

Because the query aggregates, Discover Logs switches to the **Visualization** tab to chart the result.

## Enabling the builder

A server-side setting gates the builder. Add this to `opensearch_dashboards.yml`:

```yaml
explore.enabled: true
explore.logsQueryBuilder.enabled: true
```

Restart OpenSearch Dashboards to apply the change. With the setting off, the Discover Logs page shows the standard PPL query panel.

## See also

- [Discover Logs](/docs/investigate/discover-logs/) - The Logs page the builder lives on
- [`search` command](/docs/ppl/commands/search/) - Full syntax for the expression the search box edits
- [`where` command](/docs/ppl/commands/where/) - Extended filtering beyond what filter chips offer
- [`stats` command](/docs/ppl/commands/stats/) - Full aggregation syntax, including aliases and functions the builder omits
- [PPL for DQL/Lucene Users](/docs/ppl/dql-lucene-users/) - If you are coming from the DQL search bar
