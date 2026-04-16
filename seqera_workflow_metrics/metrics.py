import logging
import re
from datetime import datetime
from typing import Any

from seqera_workflow_metrics.config import RunConfig

logger = logging.getLogger(__name__)

MS_TO_HOURS = 1000 * 60 * 60
BYTES_TO_MB = 1024 * 1024


def calculate_cpu_usage_from_tasks(
    tasks_data: dict[str, Any],
    workflow_status: str,
    config: RunConfig,
) -> dict[str, Any]:
    tasks = tasks_data.get("tasks", [])
    skip_statuses = {"NEW", "SUBMITTED", "RUNNING", "CACHED"}
    if config.exclude_failed_tasks:
        skip_statuses.update({"FAILED", "ABORTED"})

    total_cpu_hours = 0.0
    total_cpus = 0
    total_runtime_ms = 0.0
    non_cached_tasks = 0

    logger.debug(f"Analyzing {len(tasks)} total tasks for workflow status: {workflow_status}")
    logger.debug(f"Skipping tasks with statuses: {skip_statuses}")

    for i, task_item in enumerate(tasks):
        task = task_item.get("task", {})
        task_status = task.get("status")
        task_name = task.get("name", f"Task_{i}")

        if task_status in skip_statuses:
            logger.debug(f"Skipping {task_status} task: {task_name}")
            continue

        cpus = task.get("cpus", 0)
        start_time = task.get("start")
        complete_time = task.get("complete")
        realtime_ms = task.get("realtime") or 0
        task_runtime_ms = 0.0

        if config.use_start_complete_time and start_time and complete_time:
            try:
                start_dt = datetime.fromisoformat(start_time.strip('"').replace("Z", "+00:00"))
                complete_dt = datetime.fromisoformat(complete_time.strip('"').replace("Z", "+00:00"))
                task_runtime_ms = (complete_dt - start_dt).total_seconds() * 1000
                logger.debug(f"Task {task_name}: start-complete = {task_runtime_ms:.0f} ms")
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse timestamps for task {task_name}: {e}")
                continue
        elif realtime_ms > 0:
            task_runtime_ms = realtime_ms
            logger.debug(f"Task {task_name}: realtime = {task_runtime_ms:.0f} ms")
        else:
            logger.debug(f"Missing timing data for task {task_name}")
            continue

        task_cpu_ms = cpus * task_runtime_ms
        task_cpu_hours = task_cpu_ms / MS_TO_HOURS
        logger.debug(f"Task {task_name}: {cpus} CPUs x {task_runtime_ms:.0f} ms = {task_cpu_hours:.6f} CPU hours")

        total_cpu_hours += task_cpu_hours
        total_cpus += cpus
        total_runtime_ms += task_runtime_ms
        non_cached_tasks += 1

    logger.debug(f"Final: {non_cached_tasks} tasks, {total_cpus} CPUs, {total_cpu_hours:.6f} CPU hours")
    return {
        "calculated_cpu_hours": total_cpu_hours,
        "calculated_total_cpus": total_cpus,
        "calculated_total_runtime_ms": total_runtime_ms,
        "non_cached_tasks": non_cached_tasks,
    }


def parse_error_report(error_report: str) -> dict[str, str]:
    result: dict[str, str] = {"failed_process": "", "error_cause": "", "exit_code": ""}
    if not error_report:
        return result
    m = re.search(r"Error executing process > '([^']+)'", error_report)
    if m:
        result["failed_process"] = m.group(1)
    m = re.search(r"Caused by:\n\s*(.+?)(?:\n\n|\Z)", error_report, re.DOTALL)
    if m:
        result["error_cause"] = m.group(1).strip()
    elif not result["failed_process"]:
        result["error_cause"] = error_report[:200].replace("\n", " ").strip()
    m = re.search(r"Command exit status:\n\s*(\d+)", error_report)
    if m:
        result["exit_code"] = m.group(1)
    return result


def _build_default_metrics() -> dict[str, Any]:
    return {
        "workflow_id": None,
        "workflow_name": None,
        "project_name": None,
        "repository": None,
        "status": None,
        "user_name": None,
        "start_time": None,
        "end_time": None,
        "duration_ms": 0,
        "total_cpus": 0,
        "cpu_time_ms": 0,
        "cpu_efficiency": 0,
        "read_bytes": 0,
        "write_bytes": 0,
        "calculated_cpu_hours": 0,
        "calculated_total_runtime_ms": 0,
        "cached_tasks_detected": 0,
        "non_cached_tasks": 0,
        "total_data_processed_bytes": 0,
        "data_processed_mb": 0,
        "cpus_per_mb": 0,
        "failed_process": "",
        "error_cause": "",
        "exit_code": "",
        "tasks_succeeded": 0,
        "tasks_failed": 0,
        "tasks_cached_count": 0,
        "tasks_ignored": 0,
        "organization_name": "Unknown",
        "workspace_name": "Unknown",
    }


def extract_workflow_metrics(
    workflow_details: dict[str, Any],
    workflow_tasks: dict[str, Any] | None = None,
    *,
    config: RunConfig = RunConfig(),
) -> dict[str, Any]:
    workflow = workflow_details.get("workflow", {})
    metrics = _build_default_metrics()

    metrics["workflow_id"] = workflow.get("id")
    metrics["workflow_name"] = workflow.get("runName")
    metrics["project_name"] = workflow.get("projectName")
    metrics["repository"] = workflow.get("repository")
    metrics["status"] = workflow.get("status")
    metrics["user_name"] = workflow.get("userName")
    metrics["start_time"] = workflow.get("start")
    metrics["end_time"] = workflow.get("complete")
    metrics["duration_ms"] = workflow.get("duration", 0) or 0
    metrics["organization_name"] = workflow_details.get("orgName", "Unknown")
    metrics["workspace_name"] = workflow_details.get("workspaceName", "Unknown")

    error_report = workflow.get("errorReport", "") or ""
    parsed_error = parse_error_report(error_report)
    metrics["failed_process"] = parsed_error["failed_process"]
    metrics["error_cause"] = parsed_error["error_cause"]
    metrics["exit_code"] = parsed_error["exit_code"]

    workflow_stats = workflow.get("stats") or {}
    metrics["tasks_succeeded"] = workflow_stats.get("succeedCount", 0)
    metrics["tasks_failed"] = workflow_stats.get("failedCount", 0)
    metrics["tasks_cached_count"] = workflow_stats.get("cachedCount", 0)
    metrics["tasks_ignored"] = workflow_stats.get("ignoredCount", 0)

    never_started = (
        workflow.get("status") in ["FAILED", "UNKNOWN"]
        and workflow.get("start") is None
        and workflow.get("complete") is None
    )
    if never_started:
        status_note = "Workflow never started" if workflow.get("status") == "FAILED" else "Workflow status unclear"
        metrics["error_cause"] = metrics["error_cause"] or f"{status_note}; no resource stats available"
        return metrics

    progress_data = workflow_details.get("progress", {})
    wp = progress_data.get("workflowProgress", {})
    metrics["total_cpus"] = wp.get("cpus", 0)
    metrics["cpu_time_ms"] = wp.get("cpuTime", 0)
    metrics["cpu_efficiency"] = wp.get("cpuEfficiency", 0)
    metrics["read_bytes"] = wp.get("readBytes", 0)
    metrics["write_bytes"] = wp.get("writeBytes", 0)

    processes_progress = progress_data.get("processesProgress", [])
    total_cached = sum(p.get("cached", 0) for p in processes_progress)

    if workflow_tasks:
        logger.debug(f"Calculating CPU from task data for workflow {workflow.get('id')}")
        task_cpu = calculate_cpu_usage_from_tasks(workflow_tasks, workflow.get("status", "SUCCEEDED"), config)
        metrics["total_cpus"] = task_cpu["calculated_total_cpus"]
        metrics["cpu_time_ms"] = task_cpu["calculated_cpu_hours"] * MS_TO_HOURS
        metrics["calculated_cpu_hours"] = task_cpu["calculated_cpu_hours"]
        metrics["calculated_total_runtime_ms"] = task_cpu["calculated_total_runtime_ms"]
        metrics["non_cached_tasks"] = task_cpu["non_cached_tasks"]
        tasks_list = workflow_tasks.get("tasks", [])
        metrics["cached_tasks_detected"] = sum(1 for t in tasks_list if t.get("task", {}).get("status") == "CACHED")
    else:
        logger.debug(f"No task data for workflow {workflow.get('id')}, using workflow-level metrics")
        metrics["calculated_cpu_hours"] = metrics["cpu_time_ms"] / MS_TO_HOURS
        metrics["cached_tasks_detected"] = total_cached
        metrics["non_cached_tasks"] = metrics["tasks_succeeded"]

    total_data = metrics["read_bytes"] + metrics["write_bytes"]
    mb = total_data / BYTES_TO_MB if total_data > 0 else 0
    metrics["total_data_processed_bytes"] = total_data
    metrics["data_processed_mb"] = mb
    metrics["cpus_per_mb"] = metrics["total_cpus"] / mb if mb > 0 else 0

    return metrics
