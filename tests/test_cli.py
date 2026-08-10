import pandas as pd
import pytest
from typer.testing import CliRunner

from seqera_workflow_metrics.cli import app, summarize_by_user_month_workspace

runner = CliRunner()


def test_help_exits_cleanly():
    """CLI --help exits with code 0."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "workflow" in result.stdout.lower()


def test_no_args_prints_error():
    """CLI with no args should exit non-zero and mention required options."""
    result = runner.invoke(app, [])
    assert result.exit_code != 0


def _make_df(rows: list[dict]) -> pd.DataFrame:
    defaults = {
        "workflow_id": "wf1",
        "calculated_cpu_hours": 1.0,
        "tasks_succeeded": 10,
        "tasks_failed": 0,
        "organization_name": "myorg",
        "workspace_name": "mywspace",
        "user_name": "alice",
        "start_time": "2025-07-15T10:00:00Z",
        "end_time": "2025-07-15T11:00:00Z",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


class TestSummarizeByUserMonthWorkspace:
    def test_happy_path_groups_correctly(self, tmp_path):
        """Rows are grouped by org/workspace/user/month and cpu_hours summed."""
        df = _make_df([
            {"workflow_id": "wf1", "calculated_cpu_hours": 2.0, "start_time": "2025-07-01T00:00:00Z"},
            {"workflow_id": "wf2", "calculated_cpu_hours": 3.0, "start_time": "2025-07-15T00:00:00Z"},
            {"workflow_id": "wf3", "calculated_cpu_hours": 5.0, "start_time": "2025-08-01T00:00:00Z"},
        ])
        out = str(tmp_path / "metrics.csv")
        summarize_by_user_month_workspace(df, out)

        summary = pd.read_csv(str(tmp_path / "metrics_user_summary.csv"))
        assert len(summary) == 2
        july = summary[summary["month"] == "2025-07"].iloc[0]
        assert july["workflow_count"] == 2
        assert pytest.approx(july["cpu_hours"]) == 5.0
        aug = summary[summary["month"] == "2025-08"].iloc[0]
        assert aug["workflow_count"] == 1
        assert pytest.approx(aug["cpu_hours"]) == 5.0

    def test_reconciles_with_raw_totals(self, tmp_path):
        """cpu_hours, workflow_count, tasks_succeeded, tasks_failed sum to raw totals."""
        df = _make_df([
            {"workflow_id": "wf1", "calculated_cpu_hours": 1.5, "tasks_succeeded": 5, "tasks_failed": 1},
            {"workflow_id": "wf2", "calculated_cpu_hours": 2.5, "tasks_succeeded": 8, "tasks_failed": 0},
            {"workflow_id": "wf3", "calculated_cpu_hours": 0.0, "start_time": None, "end_time": None,
             "tasks_succeeded": 0, "tasks_failed": 0},
        ])
        out = str(tmp_path / "metrics.csv")
        summarize_by_user_month_workspace(df, out)

        summary = pd.read_csv(str(tmp_path / "metrics_user_summary.csv"))
        assert summary["workflow_count"].sum() == len(df)
        assert pytest.approx(summary["cpu_hours"].sum()) == df["calculated_cpu_hours"].sum()
        assert summary["tasks_succeeded"].sum() == df["tasks_succeeded"].sum()
        assert summary["tasks_failed"].sum() == df["tasks_failed"].sum()

    def test_null_start_time_falls_back_to_end_time(self, tmp_path):
        """Workflow with null start_time uses end_time for month assignment."""
        df = _make_df([
            {"workflow_id": "wf1", "start_time": None, "end_time": "2025-06-20T00:00:00Z",
             "calculated_cpu_hours": 1.0},
        ])
        out = str(tmp_path / "metrics.csv")
        summarize_by_user_month_workspace(df, out)

        summary = pd.read_csv(str(tmp_path / "metrics_user_summary.csv"))
        assert summary["month"].iloc[0] == "2025-06"

    def test_both_timestamps_null_gives_unknown_month(self, tmp_path):
        """Workflow with both start_time and end_time null appears under month='unknown'."""
        df = _make_df([
            {"workflow_id": "wf1", "start_time": None, "end_time": None, "calculated_cpu_hours": 0.0},
        ])
        out = str(tmp_path / "metrics.csv")
        summarize_by_user_month_workspace(df, out)

        summary = pd.read_csv(str(tmp_path / "metrics_user_summary.csv"))
        assert summary["month"].iloc[0] == "unknown"

    def test_null_user_name_is_preserved_not_dropped(self, tmp_path):
        """Workflows with null user_name appear in summary rather than being silently dropped."""
        df = _make_df([
            {"workflow_id": "wf1", "user_name": None, "calculated_cpu_hours": 4.0},
            {"workflow_id": "wf2", "user_name": "alice", "calculated_cpu_hours": 1.0},
        ])
        out = str(tmp_path / "metrics.csv")
        summarize_by_user_month_workspace(df, out)

        summary = pd.read_csv(str(tmp_path / "metrics_user_summary.csv"))
        assert summary["workflow_count"].sum() == 2
        assert pytest.approx(summary["cpu_hours"].sum()) == 5.0

    def test_output_path_no_csv_extension(self, tmp_path):
        """Summary path is derived correctly even when output has no .csv extension."""
        df = _make_df([{"workflow_id": "wf1"}])
        out = str(tmp_path / "metrics")
        summarize_by_user_month_workspace(df, out)

        assert (tmp_path / "metrics_user_summary").exists()
