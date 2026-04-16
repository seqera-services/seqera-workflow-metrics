from typer.testing import CliRunner
from seqera_workflow_metrics.cli import app

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
