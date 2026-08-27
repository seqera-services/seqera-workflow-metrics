import pytest
import pandas as pd
from datetime import datetime, timezone

from seqera_workflow_metrics.studios.models import CheckpointRecord, StudioRecord
from seqera_workflow_metrics.studios.metrics import (
    extract_studio_session_metrics,
    summarize_studios_by_user_month,
)
from seqera_workflow_metrics.studios.schema import STUDIOS_SCHEMA_COLUMNS


def _make_studio(cpu: int = 4, session_id: str = "abc") -> StudioRecord:
    return StudioRecord.model_validate({
        "sessionId": session_id,
        "name": "test-studio",
        "user": {"userName": "alice"},
        "configuration": {"cpu": cpu, "gpu": 0, "memory": 0},
        "computeEnv": {"id": "ce-1"},
        "statusInfo": {"status": "stopped"},
        "dateCreated": "2026-08-01T09:00:00Z",
    })


def _make_checkpoint(start: str, stop: str | None, cp_id: int = 1) -> CheckpointRecord:
    return CheckpointRecord.model_validate({
        "id": cp_id,
        "dateCreated": start,
        "dateSaved": stop,
        "status": "finalized" if stop else "active",
    })


class TestExtractStudioSessionMetrics:
    def test_complete_session_calculates_cpu_hours(self):
        studio = _make_studio(cpu=4)
        cp = _make_checkpoint("2026-08-01T10:00:00Z", "2026-08-01T12:00:00Z")
        rows = extract_studio_session_metrics(
            studio, [cp], org_name="MyOrg", workspace_name="MyWS"
        )
        assert len(rows) == 1
        assert rows[0]["cpu_hours"] == pytest.approx(8.0)  # 2h × 4 cpus
        assert rows[0]["runtime_hours"] == pytest.approx(2.0)
        assert not rows[0]["cpu_unresolved"]

    def test_cpu_zero_sets_cpu_hours_to_zero_and_flags_unresolved(self):
        studio = _make_studio(cpu=0)
        cp = _make_checkpoint("2026-08-01T10:00:00Z", "2026-08-01T12:00:00Z")
        rows = extract_studio_session_metrics(studio, [cp], org_name="O", workspace_name="W")
        assert rows[0]["cpu_hours"] == 0.0
        assert rows[0]["runtime_hours"] == pytest.approx(2.0)
        assert rows[0]["cpu_unresolved"]

    def test_incomplete_session_skipped(self):
        studio = _make_studio(cpu=4)
        cp = _make_checkpoint("2026-08-01T10:00:00Z", None)
        rows = extract_studio_session_metrics(studio, [cp], org_name="O", workspace_name="W")
        assert rows == []

    def test_multiple_checkpoints_produce_multiple_rows(self):
        studio = _make_studio(cpu=2)
        cps = [
            _make_checkpoint("2026-08-01T10:00:00Z", "2026-08-01T11:00:00Z", cp_id=1),
            _make_checkpoint("2026-08-02T10:00:00Z", "2026-08-02T12:00:00Z", cp_id=2),
        ]
        rows = extract_studio_session_metrics(studio, cps, org_name="O", workspace_name="W")
        assert len(rows) == 2
        assert rows[0]["cpu_hours"] == pytest.approx(2.0)
        assert rows[1]["cpu_hours"] == pytest.approx(4.0)

    def test_output_matches_schema(self):
        studio = _make_studio()
        cp = _make_checkpoint("2026-08-01T10:00:00Z", "2026-08-01T11:00:00Z")
        rows = extract_studio_session_metrics(studio, [cp], org_name="O", workspace_name="W")
        assert set(rows[0].keys()) == set(STUDIOS_SCHEMA_COLUMNS)

    def test_month_derived_from_session_start(self):
        studio = _make_studio()
        cp = _make_checkpoint("2026-07-15T10:00:00Z", "2026-07-15T11:00:00Z")
        rows = extract_studio_session_metrics(studio, [cp], org_name="O", workspace_name="W")
        assert rows[0]["month"] == "2026-07"


class TestSummarizeStudiosByUserMonth:
    def test_groups_by_user_workspace_month(self, tmp_path):
        rows = [
            {"studio_id": "a", "studio_name": "s1", "checkpoint_id": 1,
             "user_name": "alice", "workspace_name": "ws", "organization_name": "org",
             "session_start": "2026-07-01T10:00:00Z", "session_stop": "2026-07-01T12:00:00Z",
             "runtime_hours": 2.0, "cpu_requested": 4, "cpu_hours": 8.0,
             "cpu_unresolved": False, "month": "2026-07", "compute_env_id": "ce"},
            {"studio_id": "a", "studio_name": "s1", "checkpoint_id": 2,
             "user_name": "alice", "workspace_name": "ws", "organization_name": "org",
             "session_start": "2026-07-15T10:00:00Z", "session_stop": "2026-07-15T11:00:00Z",
             "runtime_hours": 1.0, "cpu_requested": 4, "cpu_hours": 4.0,
             "cpu_unresolved": False, "month": "2026-07", "compute_env_id": "ce"},
        ]
        df = pd.DataFrame(rows)
        out = str(tmp_path / "studios.csv")
        summarize_studios_by_user_month(df, out)
        summary = pd.read_csv(str(tmp_path / "studios_user_summary.csv"))
        assert len(summary) == 1
        assert summary["cpu_hours"].iloc[0] == pytest.approx(12.0)
        assert summary["session_count"].iloc[0] == 2

    def test_unresolved_cpu_counted_separately(self, tmp_path):
        rows = [
            {"studio_id": "a", "studio_name": "s1", "checkpoint_id": 1,
             "user_name": "alice", "workspace_name": "ws", "organization_name": "org",
             "session_start": "2026-07-01T10:00:00Z", "session_stop": "2026-07-01T12:00:00Z",
             "runtime_hours": 2.0, "cpu_requested": 0, "cpu_hours": 0.0,
             "cpu_unresolved": True, "month": "2026-07", "compute_env_id": "ce"},
        ]
        df = pd.DataFrame(rows)
        out = str(tmp_path / "studios.csv")
        summarize_studios_by_user_month(df, out)
        summary = pd.read_csv(str(tmp_path / "studios_user_summary.csv"))
        assert summary["unresolved_sessions"].iloc[0] == 1
        assert summary["cpu_hours"].iloc[0] == 0.0
        assert summary["runtime_hours"].iloc[0] == pytest.approx(2.0)
