# Seqera Workflow Metrics

A command-line tool for collecting and analyzing workflow metrics from [Seqera Platform](https://seqera.io). It queries the Platform API to retrieve per-task resource usage, computes CPU hours, and writes a structured CSV report suitable for downstream analysis or cost attribution.

---

## Prerequisites

- Python 3.10+
- A Seqera Platform account
- A Seqera Platform API token (see [Managing API tokens](https://docs.seqera.io/platform/latest/api/overview#authentication))

---

## Installation

### Standard install

```bash
pip install .
# or
uv pip install .
```

### Contributors (includes dev/test tooling)

```bash
pip install ".[dev]"
# or
uv pip install ".[dev]"
```

Dev extras include: `pytest`, `ruff`, `mypy`, `pre-commit`, and type stubs.

---

## Configuration

Set the following environment variables before running:

| Variable             | Required | Default                        | Description                              |
|----------------------|----------|--------------------------------|------------------------------------------|
| `TOWER_ACCESS_TOKEN` | Yes      | —                              | Seqera Platform API token                |
| `TOWER_API_ENDPOINT` | No       | `https://api.cloud.seqera.io`  | Override for self-hosted Platform instances |

```bash
export TOWER_ACCESS_TOKEN="your_token_here"
export TOWER_API_ENDPOINT="https://your-platform-host/api"  # optional
```

---

## API Endpoints Used

The tool calls the following Seqera Platform REST API endpoints:

| Endpoint                             | Purpose                                 |
|--------------------------------------|-----------------------------------------|
| `GET /orgs`                          | List organizations                      |
| `GET /orgs/{orgId}/workspaces`       | List workspaces in an organization      |
| `GET /workflow`                      | List workflows (with date/status filter)|
| `GET /workflow/{workflowId}`         | Retrieve workflow details and progress  |
| `GET /workflow/{workflowId}/tasks`   | Retrieve per-task resource data         |

All paginated endpoints are handled automatically.

---

## Modes of Operation

### Mode 1: Organization-based (date range)

Collects metrics for all workflows in an organization within a date window. Iterates across all workspaces automatically.

```bash
seqera-workflow-metrics \
  --org-name "MyOrg" \
  --from 2024-01-01 \
  --to 2024-03-31
```

Optional filters: `--pipeline`, `--repository`, `--status`, `--workspace-id`.

### Mode 2: Specific workflow IDs

Collects metrics for a known list of workflow IDs within a specific workspace.

```bash
seqera-workflow-metrics \
  --workflow-ids "1abc23,4def56,7ghi89" \
  --workspace-id 12345678
```

Workflow IDs can be comma-separated or space-separated.

### Mode 3: Local file input (offline analysis)

Processes pre-downloaded workflow and task JSON files without making API calls. Useful for offline analysis or CI testing.

```bash
seqera-workflow-metrics \
  --workflow-file workflow.json \
  --tasks-file workflow-tasks.json
```

The JSON files should match the schema returned by `GET /workflow/{id}` and `GET /workflow/{id}/tasks` respectively.

---

## Command Line Options

Run `seqera-workflow-metrics --help` for the full reference. Key options:

| Option                      | Short | Description                                                                 |
|-----------------------------|-------|-----------------------------------------------------------------------------|
| `--org-name`                | `-o`  | Organization name (Mode 1)                                                  |
| `--from`                    |       | Start date `YYYY-MM-DD` (Mode 1)                                            |
| `--to`                      |       | End date `YYYY-MM-DD` (Mode 1, defaults to today)                           |
| `--workflow-ids`            | `-i`  | Comma or space-separated workflow IDs (Mode 2)                              |
| `--workspace-id`            | `-w`  | Workspace ID (required for Mode 2, optional filter for Mode 1)              |
| `--workflow-file`           |       | Path to `workflow.json` (Mode 3)                                            |
| `--tasks-file`              |       | Path to `workflow-tasks.json` (Mode 3)                                      |
| `--pipeline`                | `-p`  | Filter by pipeline/project name                                             |
| `--repository`              | `-r`  | Filter by repository URL                                                    |
| `--status`                  | `-s`  | Filter by workflow status (`SUCCEEDED`, `FAILED`, etc.)                     |
| `--output`                  |       | Output CSV file path (default: `workflow_metrics.csv`)                      |
| `--endpoint`                | `-e`  | Override API endpoint URL (alternative to `TOWER_API_ENDPOINT`)             |
| `--use-start-complete-time` |       | Use wall-clock (start→complete) duration instead of `realtime` per task     |
| `--exclude-failed-tasks`    |       | Exclude `FAILED` and `ABORTED` tasks from CPU calculations                  |
| `--task-details`            |       | Print per-task calculation details to the log                               |
| `--verbose`, `-v`           | `-v`  | Enable DEBUG-level logging (more detail than `--task-details`)              |

---

## Output

### Console summary

After collection, the tool prints a summary to stdout including:

- Total workflows analyzed
- Workflow status breakdown (SUCCEEDED / FAILED / CANCELLED)
- Total and average CPU hours, data processed, CPU efficiency
- Per-workspace breakdown
- Error details for failed/aborted workflows (up to 10)

### Log file

A `.out` log file is written alongside the CSV (e.g. `workflow_metrics.out`). Use `--verbose` / `-v` to include DEBUG-level output in the log.

### CSV output

Metrics are written to `workflow_metrics.csv` (or the path given by `--output`). The schema is defined as `SCHEMA_COLUMNS` in [`seqera_workflow_metrics/schema.py`](seqera_workflow_metrics/schema.py) and is the authoritative source of truth. **Schema version: 1.0**

| Column                        | Description                                                              |
|-------------------------------|--------------------------------------------------------------------------|
| `workflow_id`                 | Unique workflow run ID                                                   |
| `workflow_name`               | Human-readable run name                                                  |
| `project_name`                | Pipeline project name                                                    |
| `repository`                  | Pipeline repository URL                                                  |
| `status`                      | Final workflow status (`SUCCEEDED`, `FAILED`, `CANCELLED`, etc.)         |
| `user_name`                   | Platform user who launched the workflow                                  |
| `start_time`                  | Workflow start timestamp (ISO 8601)                                      |
| `end_time`                    | Workflow completion timestamp (ISO 8601)                                 |
| `duration_ms`                 | Total wall-clock duration in milliseconds                                |
| `total_cpus`                  | Total CPUs allocated across all non-cached tasks                         |
| `cpu_time_ms`                 | Aggregated CPU time in milliseconds (CPUs × runtime per task)            |
| `cpu_efficiency`              | CPU efficiency as reported by Platform (%)                               |
| `read_bytes`                  | Total bytes read across all tasks                                        |
| `write_bytes`                 | Total bytes written across all tasks                                     |
| `calculated_cpu_hours`        | Calculated CPU hours (see [CPU Calculation](#cpu-calculation))           |
| `calculated_total_runtime_ms` | Sum of per-task runtime used in CPU calculation (ms)                     |
| `cached_tasks_detected`       | Number of tasks with `CACHED` status                                     |
| `non_cached_tasks`            | Number of tasks included in CPU calculations                             |
| `total_data_processed_bytes`  | Total bytes read + written                                               |
| `data_processed_mb`           | `total_data_processed_bytes` converted to MB                             |
| `cpus_per_mb`                 | Ratio of CPUs to MB processed                                            |
| `failed_process`              | Name of the process that caused failure (parsed from error report)       |
| `error_cause`                 | Error description (parsed from error report)                             |
| `exit_code`                   | Process exit code at failure (parsed from error report)                  |
| `tasks_succeeded`             | Count of tasks with `SUCCEEDED` status                                   |
| `tasks_failed`                | Count of tasks with `FAILED` status                                      |
| `tasks_cached_count`          | Count of tasks with `CACHED` status (from workflow stats)                |
| `tasks_ignored`               | Count of tasks with `IGNORED` status                                     |
| `organization_name`           | Platform organization name                                               |
| `workspace_name`              | Platform workspace name                                                  |

---

## CPU Calculation

`calculated_cpu_hours` is computed bottom-up from individual task data:

```
cpu_hours = sum(task.cpus × task.runtime_ms) / 3_600_000
```

By default, `task.runtime_ms` is sourced from the `realtime` field reported by Nextflow (actual CPU-active wall time). Pass `--use-start-complete-time` to use the wall-clock difference between `start` and `complete` timestamps instead — this includes scheduling overhead and is typically larger.

Cached tasks (`CACHED` status) are excluded from all calculations. Tasks that are still `RUNNING`, `SUBMITTED`, or `NEW` at collection time are also excluded. Pass `--exclude-failed-tasks` to additionally exclude `FAILED` and `ABORTED` tasks.

---

## Troubleshooting

**`TOWER_ACCESS_TOKEN environment variable is not set`**
Set the environment variable: `export TOWER_ACCESS_TOKEN="your_token_here"`

**`Organization 'X' not found`**
The `--org-name` value must match the organization name exactly as it appears in Seqera Platform. Check for capitalisation differences.

**`--workspace-id is required when using --workflow-ids`**
Mode 2 requires an explicit `--workspace-id` because workflow IDs are scoped to a workspace.

**No workflows returned for a date range**
- Check the `--from` / `--to` dates cover the expected period.
- Try adding `--status SUCCEEDED` to narrow the query.
- Verify your token has read access to the target organization and workspaces.

**Unexpected CPU hour values**
Run with `--task-details` to see per-task timing breakdowns in the log. Use `--verbose` for full debug output including API request/response details.

---

## Contributing

Contributions are welcome. Please follow the steps below:

1. Install with dev extras: `pip install ".[dev]"` or `uv pip install ".[dev]"`
2. Install pre-commit hooks: `pre-commit install`
3. Run the test suite: `pytest`
4. Run linting and type checks: `ruff check . && mypy .`

Pre-commit hooks enforce code style (`ruff`) and type correctness (`mypy`) on every commit. PRs should pass all checks before review.

The CSV schema (`SCHEMA_COLUMNS` in `seqera_workflow_metrics/schema.py`) is the data contract between this tool and any downstream consumers. Changes to the schema require a schema version bump.
