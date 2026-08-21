# Seqera Platform Metrics

A command-line tool for collecting and analyzing resource metrics from [Seqera Platform](https://seqera.io). It covers two metric types:

- **Workflows**: queries per-task resource usage and computes CPU hours from task-level data
- **Studios**: estimates CPU hours from Data Studios sessions using checkpoint history as a proxy for session duration

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

| Endpoint                                        | Purpose                                  |
|-------------------------------------------------|------------------------------------------|
| `GET /orgs`                                     | List organizations                       |
| `GET /orgs/{orgId}/workspaces`                  | List workspaces in an organization       |
| `GET /workflow`                                 | List workflows (with date/status filter) |
| `GET /workflow/{workflowId}`                    | Retrieve workflow details and progress   |
| `GET /workflow/{workflowId}/tasks`              | Retrieve per-task resource data          |
| `GET /studios`                                  | List Studios and their current config    |
| `GET /studios/{sessionId}/checkpoints`          | List checkpoints for a Studio session    |

All paginated endpoints are handled automatically.

---

## Entry Points

The package installs three CLI commands:

| Command                    | Description                                                                         |
|----------------------------|-------------------------------------------------------------------------------------|
| `seqera-platform-metrics`  | Multi-command CLI — use `workflows` or `studios` subcommands                        |
| `seqera-workflow-metrics`  | Standalone entry point for the workflows command (backwards compatible)             |
| `seqera-studios-metrics`   | Standalone entry point for the studios command                                      |

Each standalone command is wired directly to the same underlying function as its subcommand equivalent. They accept the same options but do **not** take a subcommand token — `seqera-workflow-metrics workflows ...` would fail.

```bash
# These pairs are equivalent:
seqera-platform-metrics workflows --org-name "MyOrg" --from 2024-01-01
seqera-workflow-metrics --org-name "MyOrg" --from 2024-01-01

seqera-platform-metrics studios --org-name "MyOrg" --from 2024-01-01
seqera-studios-metrics --org-name "MyOrg" --from 2024-01-01
```

---

## Workflows

### Modes of Operation

#### Mode 1: Organization-based (date range)

Collects metrics for all workflows in an organization within a date window. Iterates across all workspaces automatically.

```bash
seqera-workflow-metrics \
  --org-name "MyOrg" \
  --from 2024-01-01 \
  --to 2024-03-31
```

Optional filters: `--pipeline`, `--repository`, `--status`, `--workspace-id`.

#### Mode 2: Specific workflow IDs

Collects metrics for a known list of workflow IDs within a specific workspace.

```bash
seqera-workflow-metrics \
  --workflow-ids "1abc23,4def56,7ghi89" \
  --workspace-id 12345678
```

Workflow IDs can be comma-separated or space-separated.

#### Mode 3: Local file input (offline analysis)

Processes pre-downloaded workflow and task JSON files without making API calls. Useful for offline analysis or CI testing.

```bash
seqera-workflow-metrics \
  --workflow-file workflow.json \
  --tasks-file workflow-tasks.json
```

The JSON files should match the schema returned by `GET /workflow/{id}` and `GET /workflow/{id}/tasks` respectively.

---

### Command Line Options

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
| `--summarize`               |       | Write an additional CSV with CPU hours grouped by user, month, and workspace |
| `--verbose`, `-v`           | `-v`  | Enable DEBUG-level logging (more detail than `--task-details`)              |

---

## Workflows output

### Console summary

After collection, the tool prints a summary to stdout including:

- Total workflows analyzed
- Workflow status breakdown (SUCCEEDED / FAILED / CANCELLED)
- Total and average CPU hours, data processed, CPU efficiency
- Per-workspace breakdown
- Error details for failed/aborted workflows (up to 10)

### User summary CSV (`--summarize`)

Pass `--summarize` to write a second CSV alongside the main output (e.g. `workflow_metrics_user_summary.csv`). It aggregates CPU hours per user, per calendar month, per workspace — useful for cost attribution across teams or environments.

```bash
seqera-workflow-metrics \
  --org-name "MyOrg" \
  --from 2024-01-01 \
  --to 2024-03-31 \
  --summarize
# produces: workflow_metrics.csv + workflow_metrics_user_summary.csv
```

| Column           | Description                                          |
|------------------|------------------------------------------------------|
| `organization_name` | Platform organization name                        |
| `workspace_name` | Platform workspace name                              |
| `user_name`      | Platform user who launched the workflows             |
| `month`          | Calendar month (`YYYY-MM`), or `unknown` for workflows with no timestamp |
| `workflow_count` | Number of workflow runs in that group                |
| `cpu_hours`      | Total calculated CPU hours                           |
| `tasks_succeeded`| Total tasks succeeded                                |
| `tasks_failed`   | Total tasks failed                                   |

The totals in this file are guaranteed to reconcile with the main CSV — every workflow row is represented, including runs that failed before launch (which appear under `month=unknown` with `cpu_hours=0`).

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

## Studios

Collects approximate CPU hours for Data Studios sessions. Because the Platform API does not expose session history, this uses checkpoint timestamps as a proxy for session duration and the studio's current CPU configuration as the CPU count.

Requires `TOWER_ACCESS_TOKEN` to be set (see [Configuration](#configuration)). For self-hosted Platform instances, also set `TOWER_API_ENDPOINT`. The Studios API endpoints (`GET /studios`, `GET /studios/{sessionId}/checkpoints`) were introduced in Platform v25.3 — earlier versions will return a 404 for these endpoints.

```bash
seqera-studios-metrics \
  --org-name "MyOrg" \
  --from 2024-01-01 \
  --to 2024-03-31

# or with the multi-command entry point:
seqera-platform-metrics studios \
  --org-name "MyOrg" \
  --from 2024-01-01 \
  --to 2024-03-31
```

### Command Line Options

Run `seqera-studios-metrics --help` for the full reference. Key options:

| Option           | Short | Description                                                              |
|------------------|-------|--------------------------------------------------------------------------|
| `--org-name`     | `-o`  | Organization name (required)                                             |
| `--from`         |       | Start date `YYYY-MM-DD` (required)                                       |
| `--to`           |       | End date `YYYY-MM-DD` (defaults to today)                                |
| `--workspace-id` | `-w`  | Filter to a specific workspace                                           |
| `--output`       |       | Output CSV file path (default: `studios_metrics.csv`)                    |
| `--summarize`    |       | Write an additional CSV grouped by user, month, and workspace            |
| `--endpoint`     | `-e`  | Override API endpoint URL                                                |
| `--verbose`      | `-v`  | Enable DEBUG-level logging                                               |

### Studios CSV output

| Column             | Description                                                                       |
|--------------------|-----------------------------------------------------------------------------------|
| `studio_id`        | Studio session ID                                                                 |
| `studio_name`      | Studio display name                                                               |
| `checkpoint_id`    | Checkpoint ID (one row per completed checkpoint)                                  |
| `user_name`        | Platform user who created the studio                                              |
| `workspace_name`   | Platform workspace name                                                           |
| `organization_name`| Platform organization name                                                        |
| `session_start`    | Checkpoint creation timestamp — used as session start proxy (ISO 8601)            |
| `session_stop`     | Checkpoint saved timestamp — used as session stop proxy (ISO 8601)                |
| `runtime_hours`    | Wall-clock duration of the session in hours (elapsed time from start to stop, regardless of CPU count) |
| `cpu_requested`    | CPU count from current studio configuration                                       |
| `cpu_hours`        | Estimated compute consumption: `cpu_requested × runtime_hours`. Two users who ran for the same duration on different instance sizes will have different CPU hours. 0 when `cpu_unresolved=True` |
| `cpu_unresolved`   | `True` when `cpu_requested=0` (studio inherits CE default — CPU count unknown)    |
| `month`            | Calendar month of session start (`YYYY-MM`)                                       |
| `compute_env_id`   | Compute environment ID associated with the studio                                 |

### Studios CPU hours: methodology and limitations

Studios CPU hours are an **approximation**. The Platform API does not expose session history or runtime metering for studios on customer-managed compute environments. This tool uses the following heuristic:

```
cpu_hours ≈ cpu_requested × (checkpoint.dateSaved − checkpoint.dateCreated)
```

**Key caveats:**

- **`cpu_requested` is the current config, not historical.** If a studio's CPU setting was changed after sessions ran, earlier sessions will be attributed the wrong CPU count. The value at collection time is used for all checkpoints of that studio.
- **`cpu_requested = 0` means "inherit CE default."** These studios have `cpu_unresolved=True` and `cpu_hours=0` in the output — runtime is still recorded so totals can be partially computed.
- **Checkpoints proxy sessions, not individual runs.** A checkpoint represents a saved environment state, not necessarily a discrete compute session. The timestamp delta is the best available approximation for time spent running.
- **Not billing-accurate.** Actual cloud cost depends on the provisioned instance type, not the requested CPU count.
- **Date filtering is on session start, not stop.** A checkpoint whose `dateCreated` falls outside `--from`/`--to` is excluded even if it completed within the window. Sessions that straddle a window boundary will be dropped rather than partially counted.

These figures are suitable for relative comparisons and rough cost attribution across workspaces and users. They should not be treated as exact compute consumption.

### Log file

A `.out` log file is written alongside the CSV (e.g. `studios_metrics.out`). Use `--verbose` / `-v` to include DEBUG-level output.

### Studios user summary CSV (`--summarize`)

Pass `--summarize` to write a second CSV (e.g. `studios_metrics_user_summary.csv`) aggregating by user, month, and workspace:

| Column               | Description                                                    |
|----------------------|----------------------------------------------------------------|
| `organization_name`  | Platform organization name                                     |
| `workspace_name`     | Platform workspace name                                        |
| `user_name`          | Platform user who created the studio                           |
| `month`              | Calendar month (`YYYY-MM`)                                     |
| `session_count`      | Number of completed checkpoint sessions in that group          |
| `runtime_hours`      | Total wall-clock hours across all sessions in the group        |
| `cpu_hours`          | Total estimated CPU hours (`cpu_requested × runtime_hours` per session) |
| `unresolved_sessions`| Count of sessions where CPU could not be resolved (`cpu=0`)    |

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
