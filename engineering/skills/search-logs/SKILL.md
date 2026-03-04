---
name: search-logs
description: Search and analyze logs in Elasticsearch for applications deployed in the infrastructure. Use when investigating errors, debugging issues, analyzing traffic patterns, or monitoring application behavior.
allowed-tools: Bash, Read, Grep, Glob
---

# Search Logs Skill

This skill helps search for logs in Elasticsearch for Flashscore Frontend applications.

## Elasticsearch

**When investigating Icinga alerts:** get `es_host`, `es_index`, `es_query`, `es_time` from `attrs.vars` of the Icinga service object. Auth is always `$ES_USER`:`$ES_PASS` (env vars) — never use `es_username`/`es_password` from Icinga vars.

### felog cluster (Flashscore Frontend — primary for Icinga alerts)

- **Endpoint:** `http://felogesdb-client.tt2.lsapp.tech:9200`
- **Auth:** `$ES_USER:$ES_PASS`
- **Index pattern:** `app-fe-flashscore-web-*`
- **Retention:** 10–14 days (daily data streams: `.ds-app-fe-flashscore-web-14d-YYYY.MM.DD-*`)

**Document structure:** Each `_source` has two representations of the same log entry:

- `message` — raw JSON string as received (avoid parsing this; it contains escaped unicode)
- `json.log.*` — Logstash-parsed fields, ready to use directly in `jq` and queries

**Always use `json.log.*` paths in `jq`** — do not parse `message` with `fromjson`:

```bash
curl -s -u "$ES_USER:$ES_PASS" \
  "http://felogesdb-client.tt2.lsapp.tech:9200/app-fe-flashscore-web-*/_search" \
  -H "Content-Type: application/json" \
  -d '{"size":20,"sort":[{"@timestamp":"desc"}],"query":{"bool":{"must":[{"query_string":{"query":"<es_query>"}}],"filter":[{"range":{"@timestamp":{"gte":"now-1h"}}}]}}}' \
  | jq -r '.hits.hits[]._source | [.["@timestamp"], .agent.hostname, .json.log.logname, .json.log.loglevel, .json.log.message] | @tsv'
```

For **SQL errors** (`logname:/sql.*/`), `json.log.messageData` contains extra context — include it when relevant:

```bash
  | jq -r '.hits.hits[]._source | [.["@timestamp"], .agent.hostname, .json.log.logname, .json.log.loglevel, .json.log.message, .json.log.messageData["mysql.errorCode"], .json.log.messageData["mysql.connection.host"]] | @tsv'
```

For **PHP errors** (`logname:"web.err"` with `loglevel:error`), `json.log.messageData` contains exception details:

```bash
  | jq -r '.hits.hits[]._source | [.["@timestamp"], .agent.hostname, .json.log.loglevel, .json.log.message, .json.log.messageData["exception.Class"], .json.log.messageData["exception.File"], (.json.log.messageData["exception.line"] | tostring)] | @tsv'
```

**Queryable fields** (use in `query_string` / `term` filters):

| Field                                        | Description                                                             |
| -------------------------------------------- | ----------------------------------------------------------------------- |
| `agent.hostname`                             | Server hostname (e.g. `fsweb19-tt2`, `fscpu2-tt2`)                      |
| `json.log.logname`                           | Log file name (e.g. `sql-dcmydbrs.fsdbcon.tt2.lssrv.tech-datacore.err`) |
| `json.log.loglevel`                          | Level: `error`, `warning`, `info`, `stats`                              |
| `json.log.message`                           | Log message text                                                        |
| `json.log.hostname`                          | Application-reported hostname                                           |
| `json.log.messageData`                       | Structured context object (varies by log type — see below)              |
| `json.log.messageData.mysql.errorCode`       | MySQL error code (SQL logs only, e.g. `2006`, `4031`)                   |
| `json.log.messageData.mysql.connection.host` | DB host that failed (SQL logs only)                                     |
| `json.log.messageData.exception.Class`       | PHP exception class (web.err error logs only)                           |
| `json.log.messageData.exception.File`        | PHP file where exception was thrown                                     |
| `json.log.messageData.exception.line`        | Line number                                                             |
| `@timestamp`                                 | Log timestamp                                                           |

## Instructions

### 1. Search Logs

Replay the exact Icinga query with a longer time window to fetch actual log entries:

```bash
curl -s -u "$ES_USER:$ES_PASS" \
  "http://<es_host>:9200/<es_index>/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 50,
    "sort": [{"@timestamp": {"order": "desc"}}],
    "query": {
      "bool": {
        "must": [{"query_string": {"query": "<es_query>"}}],
        "filter": [{"range": {"@timestamp": {"gte": "now-1h"}}}]
      }
    }
  }'
```

### 2. Time Filters

```json
{"range": {"@timestamp": {"gte": "now-1h"}}}     // last hour
{"range": {"@timestamp": {"gte": "now-24h"}}}    // last 24 hours
{"range": {"@timestamp": {"gte": "now-7d"}}}     // last 7 days
{"range": {"@timestamp": {"gte": "2025-10-06T00:00:00"}}}  // from specific time
```

### 3. Useful Aggregations

**Distinct lognames or messages (useful for understanding alert scope):**

```bash
curl -s -u "$ES_USER:$ES_PASS" \
  "http://<es_host>:9200/<es_index>/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "query": {"bool": {"must": [{"query_string": {"query": "<es_query>"}}], "filter": [{"range": {"@timestamp": {"gte": "now-1h"}}}]}},
    "aggs": {
      "lognames": {"terms": {"field": "json.log.logname.keyword", "size": 20}},
      "messages": {"terms": {"field": "json.log.message.keyword", "size": 10}}
    }
  }'
```

**Count only** (use `/_count` instead of `/_search` with no `size`/`aggs`):

```bash
curl -s -u "$ES_USER:$ES_PASS" \
  "http://<es_host>:9200/<es_index>/_count" \
  -H "Content-Type: application/json" \
  -d '{"query": {"bool": {"must": [{"query_string": {"query": "<es_query>"}}], "filter": [{"range": {"@timestamp": {"gte": "now-5m"}}}]}}}'
```

## Tips

- For exact match use `.keyword` field (e.g., `json.log.logname.keyword`)
- For fulltext search use field without `.keyword`
- Use `size: 0` with aggregations for faster responses when you don't need raw docs
- For large results increase `size` parameter (default 10, max ~10000)
- **Never parse `message` with `fromjson`** — use `json.log.*` paths directly; Logstash already parsed them
- `json.log.messageData` keys use dot notation (e.g., `"mysql.errorCode"`) — in `jq` access as `.json.log.messageData["mysql.errorCode"]`
