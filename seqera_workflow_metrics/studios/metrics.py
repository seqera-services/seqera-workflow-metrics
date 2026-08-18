import logging
from pathlib import Path
from typing import Any

import pandas as pd

from seqera_workflow_metrics.studios.models import CheckpointRecord, StudioRecord

logger = logging.getLogger(__name__)


def extract_studio_session_metrics(
    studio: StudioRecord,
    checkpoints: list[CheckpointRecord],
    *,
    org_name: str,
    workspace_name: str,
) -> list[dict[str, Any]]:
    rows = []
    for cp in checkpoints:
        if not cp.is_complete:
            logger.debug(f"Skipping in-progress checkpoint {cp.checkpoint_id} for studio {studio.session_id}")
            continue
        runtime_hours = cp.runtime_hours  # guaranteed non-None when is_complete
        cpu_hours = 0.0 if studio.cpu_unresolved else studio.cpu * runtime_hours
        month = cp.date_created.strftime("%Y-%m")
        rows.append({
            "studio_id": studio.session_id,
            "studio_name": studio.name,
            "checkpoint_id": cp.checkpoint_id,
            "user_name": studio.user_name,
            "workspace_name": workspace_name,
            "organization_name": org_name,
            "session_start": cp.date_created.isoformat(),
            "session_stop": cp.date_saved.isoformat() if cp.date_saved else "",
            "runtime_hours": runtime_hours,
            "cpu_requested": studio.cpu,
            "cpu_hours": cpu_hours,
            "cpu_unresolved": studio.cpu_unresolved,
            "month": month,
            "compute_env_id": studio.compute_env_id,
        })
    return rows


def summarize_studios_by_user_month(df: pd.DataFrame, output: str) -> None:
    summary = (
        df.groupby(["organization_name", "workspace_name", "user_name", "month"], dropna=False)
        .agg(
            session_count=("checkpoint_id", "count"),
            runtime_hours=("runtime_hours", "sum"),
            cpu_hours=("cpu_hours", "sum"),
            unresolved_sessions=("cpu_unresolved", "sum"),
        )
        .reset_index()
        .sort_values(["organization_name", "workspace_name", "month", "cpu_hours", "user_name"],
                     ascending=[True, True, True, False, True])
    )
    summary_path = str(Path(output).with_stem(Path(output).stem + "_user_summary"))
    summary.to_csv(summary_path, index=False)
    logger.info(f"Studios user summary saved to {summary_path}")
    print(summary.to_string(index=False))
