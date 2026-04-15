"""Runtime configuration bundling CLI options."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RunConfig:
    """Bundles CLI flags passed through the call chain."""

    use_start_complete_time: bool = False
    exclude_failed_tasks: bool = False
    task_details: bool = False
    verbose: bool = False
    output: str = "workflow_metrics.csv"
