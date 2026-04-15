# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-04-15

### Added
- Initial release migrated from internal tooling
- Three modes of operation: organization-based, workflow-specific, file input
- Task-level CPU hour calculations with cached task handling
- Error report parsing with structured failure details
- CSV output with 30-column schema (schema version 1.0)
- Support for `--exclude-failed-tasks` and `--use-start-complete-time` flags
- Workspace-level aggregated statistics
