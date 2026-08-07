import json
import logging
import os
import sys
from datetime import date, datetime
from typing import Any

import pandas as pd
import typer

from seqera_workflow_metrics.client import APIClient
from seqera_workflow_metrics.config import RunConfig
from seqera_workflow_metrics.metrics import MS_TO_HOURS, extract_workflow_metrics

logger = logging.getLogger(__name__)

app = typer.Typer(help="Collect and analyze workflow metrics from Seqera Platform")


def setup_logging(output_file: str, verbose: bool = False) -> None:
    log_filename = output_file.replace(".csv", ".out")
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_filename), logging.StreamHandler()],
    )


def get_organization_lookup(client: APIClient) -> dict[str, str]:
    orgs = client.organizations()
    return {org.get("name"): org.get("orgId") for org in orgs.get("organizations", [])}


def process_workflow(
    client: APIClient, workflow_id: str, workspace_id: str, config: RunConfig
) -> dict[str, Any] | None:
    workflow_details = client.workflow_details(workflow_id, workspace_id)
    if not workflow_details:
        logger.warning(f"Could not retrieve data for workflow {workflow_id}")
        return None
    workflow_tasks = client.workflow_tasks(workflow_id, workspace_id)
    summary = extract_workflow_metrics(workflow_details, workflow_tasks, config=config)
    logger.info(f"Collected metrics for workflow {workflow_id}")
    return summary


def process_workspace_workflows(
    client: APIClient,
    workspace: dict[str, Any],
    min_time: str,
    max_time: str,
    config: RunConfig,
    **filters: Any,
) -> list[dict[str, Any]]:
    workspace_id = workspace.get("id")
    workspace_name = workspace.get("name")
    logger.info(f"Processing workspace: {workspace_name}")

    workflows = client.list_workflows(workspace_id, min_time, max_time, **filters)
    logger.info(f"Found {len(workflows)} matching workflows in workspace {workspace_name}")

    summaries: list[dict[str, Any]] = []
    for workflow in workflows:
        workflow_id = workflow.get("workflow", {}).get("id")
        summary = process_workflow(client, workflow_id, workspace_id, config)
        if summary:
            summaries.append(summary)
    return summaries


def process_specific_workflows(
    client: APIClient,
    workflow_ids: list[str],
    workspace_id: str,
    config: RunConfig,
) -> list[dict[str, Any]]:
    logger.info(f"Processing {len(workflow_ids)} specific workflows")
    summaries: list[dict[str, Any]] = []
    for workflow_id in workflow_ids:
        logger.info(f"Processing workflow ID: {workflow_id}")
        summary = process_workflow(client, workflow_id, workspace_id, config)
        if summary:
            summaries.append(summary)
    return summaries


def process_organization(
    client: APIClient,
    org_id: str,
    min_time: str,
    max_time: str,
    config: RunConfig,
    workspace_id: str | None = None,
    **filters: Any,
) -> list[dict[str, Any]]:
    workspaces_response = client.workspaces(org_id)
    workspaces = workspaces_response.get("workspaces", [])
    logger.info(f"Found {len(workspaces)} workspaces in organization")

    if workspace_id:
        workspaces = [ws for ws in workspaces if str(ws.get("id")) == str(workspace_id)]
        if workspaces:
            logger.info("Found specified workspace:")
            for ws in workspaces:
                logger.info(f"  - {ws.get('name')} (ID: {ws.get('id')})")
        else:
            logger.info(f"Specified workspace ID {workspace_id} not found in organization")

    all_summaries: list[dict[str, Any]] = []
    for workspace in workspaces:
        summaries = process_workspace_workflows(client, workspace, min_time, max_time, config, **filters)
        all_summaries.extend(summaries)
    return all_summaries


def load_workflow_data_from_files(workflow_file: str, tasks_file: str) -> dict[str, Any]:
    try:
        with open(workflow_file) as f:
            workflow_data = json.load(f)
        with open(tasks_file) as f:
            tasks_data = json.load(f)
        logger.info(f"Loaded workflow data from {workflow_file}")
        logger.info(f"Loaded {len(tasks_data)} tasks from {tasks_file}")
        return {"workflow": workflow_data, "tasks": tasks_data, "total": len(tasks_data)}
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in file: {e}")
        return {}


def convert_raw_workflow_data(
    workflow_data: dict[str, Any], tasks_data: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    converted_tasks = [{"task": task} for task in tasks_data]
    workflow_details = {
        "workflow": workflow_data,
        "orgName": "Unknown",
        "workspaceName": "Unknown",
        "progress": {
            "workflowProgress": {
                "cpus": 0,
                "cpuTime": 0,
                "cpuEfficiency": 0,
                "readBytes": 0,
                "writeBytes": 0,
            },
            "processesProgress": [],
        },
    }
    tasks_response = {"tasks": converted_tasks, "total": len(converted_tasks)}
    return workflow_details, tasks_response


def process_workflow_from_files(workflow_file: str, tasks_file: str, config: RunConfig) -> dict[str, Any] | None:
    logger.info(f"Processing workflow data from files: {workflow_file}, {tasks_file}")
    raw_data = load_workflow_data_from_files(workflow_file, tasks_file)
    if not raw_data:
        return None
    workflow_details, tasks_response = convert_raw_workflow_data(raw_data["workflow"], raw_data["tasks"])
    summary = extract_workflow_metrics(workflow_details, tasks_response, config=config)
    logger.info(f"Collected metrics for workflow {raw_data['workflow'].get('id', 'unknown')}")
    return summary


def parse_workflow_ids(workflow_ids_str: str) -> list[str]:
    if not workflow_ids_str:
        return []
    ids: list[str] = []
    for item in workflow_ids_str.split(","):
        ids.extend(item.strip().split())
    return [wid.strip() for wid in ids if wid.strip()]


def calculate_workspace_stats(df_summary: pd.DataFrame) -> pd.DataFrame:
    agg_dict = {
        "total_cpus": "sum",
        "data_processed_mb": "sum",
        "cpu_efficiency": "mean",
        "workflow_id": "count",
        "duration_ms": "mean",
        "cpus_per_mb": "mean",
        "cached_tasks_detected": "sum",
        "calculated_cpu_hours": "sum",
        "calculated_total_runtime_ms": "sum",
        "non_cached_tasks": "sum",
        "tasks_succeeded": "sum",
        "tasks_failed": "sum",
    }
    return df_summary.groupby(["organization_name", "workspace_name"]).agg(agg_dict).reset_index()


def summarize_by_user_month_workspace(df_summary: pd.DataFrame, output: str) -> None:
    from pathlib import Path

    df = df_summary.copy()
    # Workflows that never started have null start_time; fall back to end_time, then "unknown"
    timestamp = pd.to_datetime(df["start_time"], utc=True).fillna(pd.to_datetime(df["end_time"], utc=True))
    df["month"] = (
        timestamp.dt.tz_convert(None).dt.to_period("M").astype(str).where(timestamp.notna(), other="unknown")
    )
    summary = (
        df.groupby(["organization_name", "workspace_name", "user_name", "month"], dropna=False)
        .agg(
            workflow_count=("workflow_id", "count"),
            cpu_hours=("calculated_cpu_hours", "sum"),
            tasks_succeeded=("tasks_succeeded", "sum"),
            tasks_failed=("tasks_failed", "sum"),
        )
        .reset_index()
        .sort_values(
            ["organization_name", "workspace_name", "month", "cpu_hours", "user_name"],
            ascending=[True, True, True, False, True],
        )
    )
    summary_path = str(Path(output).with_stem(Path(output).stem + "_user_summary"))
    summary.to_csv(summary_path, index=False)
    logger.info(f"User summary saved to {summary_path}")
    print(summary.to_string(index=False))


def display_summary_statistics(df_summary: pd.DataFrame) -> None:
    total_workflows = len(df_summary)
    workflows_with_cached_tasks = len(df_summary[df_summary["cached_tasks_detected"] > 0])
    total_cached_tasks = df_summary["cached_tasks_detected"].sum()
    total_calculated_cpu_hours = df_summary["calculated_cpu_hours"].sum()

    stats = {
        "Total workflows analyzed": total_workflows,
        "Workflows with cached tasks": workflows_with_cached_tasks,
        "Total cached tasks detected": total_cached_tasks,
        "Total CPUs used": f"{df_summary['total_cpus'].sum():,.2f}",
        "Total calculated CPU hours": f"{total_calculated_cpu_hours:,.2f}",
        "Total data processed": f"{df_summary['data_processed_mb'].sum():,.2f} MB",
        "Average CPU efficiency": f"{df_summary['cpu_efficiency'].mean():.2f}%",
        "Average CPUs per MB": f"{df_summary['cpus_per_mb'].mean():.4f}",
        "Average workflow duration": f"{df_summary['duration_ms'].mean() / MS_TO_HOURS:.2f} hours",
    }

    print("\nWorkflow Metrics Summary:")
    for label, value in stats.items():
        print(f"{label}: {value}")

    print("\nWorkflow Status Breakdown:")
    status_counts = df_summary["status"].value_counts()
    for status, count in status_counts.items():
        pct = count / total_workflows * 100
        print(f"  {status}: {count} ({pct:.1f}%)")

    total_tasks_failed = df_summary["tasks_failed"].sum()
    total_tasks_succeeded = df_summary["tasks_succeeded"].sum()
    if total_tasks_failed > 0:
        print("\nTask-Level Failure Summary:")
        print(f"  Total tasks succeeded: {int(total_tasks_succeeded)}")
        print(f"  Total tasks failed: {int(total_tasks_failed)}")

    print("\nMetrics by Workspace:")
    workspace_stats = calculate_workspace_stats(df_summary)
    status_by_workspace = (
        df_summary.groupby(["organization_name", "workspace_name", "status"]).size().unstack(fill_value=0).reset_index()
    )
    workspace_stats = workspace_stats.merge(status_by_workspace, on=["organization_name", "workspace_name"], how="left")

    for _, row in workspace_stats.iterrows():
        failed_runs = int(row.get("FAILED", 0))
        succeeded_runs = int(row.get("SUCCEEDED", 0))
        cancelled_runs = int(row.get("CANCELLED", 0))
        print(f"\nOrg: {row['organization_name']} - Workspace: {row['workspace_name']}")
        print(
            f"  Workflows: {row['workflow_id']} "
            f"(succeeded: {succeeded_runs}, failed: {failed_runs}, cancelled: {cancelled_runs})"
        )
        print(f"  Total CPUs: {row['total_cpus']:,.2f}")
        print(f"  Calculated CPU hours: {row['calculated_cpu_hours']:,.2f}")
        print(f"  Cached tasks: {row['cached_tasks_detected']:,.0f}")
        print(f"  Non-cached tasks: {row['non_cached_tasks']:,.0f}")
        if row["tasks_failed"] > 0:
            print(f"  Task failures: {int(row['tasks_failed'])}")
        print(f"  Data processed: {row['data_processed_mb']:,.2f} MB")
        print(f"  Avg CPU efficiency: {row['cpu_efficiency']:.2f}%")
        print(f"  Avg CPUs per MB: {row['cpus_per_mb']:.4f}")
        print(f"  Avg duration: {row['duration_ms'] / MS_TO_HOURS:.2f} hours")

    failed_workflows = df_summary[
        (df_summary["status"].isin(["FAILED", "ABORTED", "CANCELLED"])) & (df_summary["error_cause"] != "")
    ]
    if not failed_workflows.empty:
        print(f"\nError Details ({len(failed_workflows)} failed/aborted workflows):")
        for _, row in failed_workflows.head(10).iterrows():
            print(f"  [{row['status']}] {row['organization_name']}/{row['workspace_name']} - {row['workflow_name']}:")
            if row["failed_process"]:
                print(f"    Process: {row['failed_process']}")
            print(f"    Cause: {row['error_cause'][:150]}")
            if row["exit_code"]:
                print(f"    Exit code: {row['exit_code']}")


def save_metrics_to_files(workflow_summaries: list[dict[str, Any]], output: str, summarize: bool = False) -> None:
    if not workflow_summaries:
        logger.warning("No workflow data collected")
        print("No workflow data collected. Check your filters or date range.")
        return
    df_summary = pd.DataFrame(workflow_summaries)
    df_summary.to_csv(output, index=False)
    logger.info(f"Workflow metrics saved to {output}")
    display_summary_statistics(df_summary)
    if summarize:
        summarize_by_user_month_workspace(df_summary, output)


@app.command()
def main(
    org_name: str | None = typer.Option(
        None,
        "--org-name",
        "-o",
        help="Organization name to analyze (required unless using workflow IDs or file input)",
    ),
    from_date: datetime | None = typer.Option(
        None,
        "--from",
        help="Start date (YYYY-MM-DD) (required unless using workflow IDs or file input)",
    ),
    to_date: datetime | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)"),
    pipeline: str | None = typer.Option(
        None,
        "--pipeline",
        "-p",
        help="Filter by pipeline name",
    ),
    repository: str | None = typer.Option(
        None,
        "--repository",
        "-r",
        help="Filter by repository URL",
    ),
    output: str = typer.Option("workflow_metrics.csv", "--output", help="Output CSV file path"),
    workspace_id: str | None = typer.Option(
        None,
        "--workspace-id",
        "-w",
        help="Specific workspace ID",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by workflow status",
    ),
    endpoint: str | None = typer.Option(
        None,
        "--endpoint",
        "-e",
        help="Platform API endpoint URL",
    ),
    workflow_ids: str | None = typer.Option(
        None,
        "--workflow-ids",
        "-i",
        help="Workflow IDs (comma or space separated)",
    ),
    workflow_file: str | None = typer.Option(
        None,
        "--workflow-file",
        help="Path to workflow.json file",
    ),
    tasks_file: str | None = typer.Option(
        None,
        "--tasks-file",
        help="Path to workflow-tasks.json file",
    ),
    use_start_complete_time: bool = typer.Option(
        False,
        "--use-start-complete-time",
        help="Use start-complete duration instead of realtime for CPU calculations",
    ),
    exclude_failed_tasks: bool = typer.Option(
        False,
        "--exclude-failed-tasks",
        help="Exclude FAILED and ABORTED tasks from CPU calculations",
    ),
    task_details: bool = typer.Option(
        False,
        "--task-details",
        help="Show detailed task-level calculations",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable debug logging",
    ),
    summarize: bool = typer.Option(
        False,
        "--summarize",
        help="Output an additional CSV with CPU hours grouped by user, month, and workspace",
    ),
) -> None:
    """Collect and analyze workflow metrics from Seqera Platform.

    Three modes of operation:

    1. Organization-based: --org-name and --from to analyze workflows in date range

    2. Workflow-specific: --workflow-ids and --workspace-id for specific workflows

    3. File input: --workflow-file and --tasks-file for offline analysis
    """
    setup_logging(output, verbose)

    config = RunConfig(
        use_start_complete_time=use_start_complete_time,
        exclude_failed_tasks=exclude_failed_tasks,
        task_details=task_details,
        verbose=verbose,
        output=output,
    )

    # File input mode
    if workflow_file and tasks_file:
        logger.info("Using file input mode")
        summary = process_workflow_from_files(workflow_file, tasks_file, config)
        if summary:
            workflow_summaries = [summary]
        else:
            logger.error("Failed to process workflow data from files")
            sys.exit(1)
    else:
        # API-based modes
        base_url = endpoint or os.getenv("TOWER_API_ENDPOINT", "https://api.cloud.seqera.io")
        api_key = os.getenv("TOWER_ACCESS_TOKEN")
        if not api_key:
            logger.error("TOWER_ACCESS_TOKEN environment variable is not set")
            sys.exit(1)

        client = APIClient(base_url, api_key)

        if workflow_ids:
            if not workspace_id:
                logger.error("--workspace-id is required when using --workflow-ids")
                sys.exit(1)
            workflow_summaries = process_specific_workflows(
                client, parse_workflow_ids(workflow_ids), workspace_id, config
            )
        else:
            if not org_name:
                logger.error("--org-name is required when not using --workflow-ids or file input")
                sys.exit(1)
            if not from_date:
                logger.error("--from date is required when not using --workflow-ids or file input")
                sys.exit(1)

            to_date = to_date or datetime.combine(date.today(), datetime.max.time())

            org_lookup = get_organization_lookup(client)
            org_id = org_lookup.get(org_name)
            if not org_id:
                logger.error(f"Organization '{org_name}' not found")
                sys.exit(1)

            logger.info(f"Found organization ID {org_id} for '{org_name}'")

            min_time = datetime.combine(from_date.date(), datetime.min.time()).isoformat(timespec="milliseconds") + "Z"
            max_time = datetime.combine(to_date.date(), datetime.max.time()).isoformat(timespec="milliseconds") + "Z"

            workflow_summaries = process_organization(
                client,
                org_id,
                min_time,
                max_time,
                config,
                workspace_id=workspace_id,
                pipeline=pipeline,
                repository=repository,
                status=status,
            )

    save_metrics_to_files(workflow_summaries, output, summarize=summarize)
