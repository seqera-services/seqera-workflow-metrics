# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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
