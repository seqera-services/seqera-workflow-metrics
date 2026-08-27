# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.3.0] - 2026-08-18

### Added
- `studios` subcommand: estimates CPU hours for Studios sessions using a checkpoint-based heuristic
- `seqera-platform-metrics` entry point: multi-command CLI (`workflows` + `studios` subcommands)
- `seqera-studios-metrics` entry point: standalone studios command
- Pydantic v2 models for Studios API data (`StudioRecord`, `CheckpointRecord`)
- `--summarize` flag for studios: writes `<output>_user_summary.csv` grouped by user/month/workspace

### Notes
- Studios CPU hours use a heuristic: `cpu_requested × (checkpoint.dateSaved − checkpoint.dateCreated)`. The Platform API does not expose session history or runtime metering for studios on customer-managed compute environments — checkpoint timestamps are the best available proxy for session duration.
- Studios with `cpu=0` (CE default, CPU count unknown) emit `cpu_unresolved=True` and `cpu_hours=0`; runtime is still recorded.
- `cpu_requested` reflects the studio's configuration at collection time. If the CPU setting was changed after sessions ran, earlier sessions are attributed the current value.
- `seqera-workflow-metrics` entry point preserved as backwards-compatible alias for the `workflows` subcommand.

## [0.2.0] - 2026-08-10

### Added
- `--summarize` flag: writes a second CSV (`<output>_user_summary.csv`) grouping CPU hours by user, month, and workspace for cost attribution

### Fixed
- Workflows with `null start_time` (failed before launch) were silently dropped from the user summary; they now fall back to `end_time` and appear under `month=unknown`
- Workspace listing incorrectly used paginated requests; the endpoint returns all results in a single response and is now called with a plain GET

## [0.1.0] - 2026-04-15

### Added
- Initial release migrated from internal tooling
- Three modes of operation: organization-based, workflow-specific, file input
- Task-level CPU hour calculations with cached task handling
- Error report parsing with structured failure details
- CSV output with 30-column schema (schema version 1.0)
- Support for `--exclude-failed-tasks` and `--use-start-complete-time` flags
- Workspace-level aggregated statistics
