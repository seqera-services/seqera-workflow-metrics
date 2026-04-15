import pytest
from unittest.mock import patch
from seqera_workflow_metrics.client import APIClient


@pytest.fixture
def client():
    return APIClient("https://api.example.com", "test-token")


class TestPaginate:
    def test_single_page(self, client):
        """Single page of results returns all items."""
        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {
                "items": [{"id": 1}, {"id": 2}],
                "totalSize": 2,
            }
            result = client._paginate("endpoint", {}, "items", "totalSize")
            assert len(result) == 2
            assert mock_get.call_count == 1

    def test_multi_page(self, client):
        """Multiple pages are fetched until total is reached."""
        with patch.object(client, "get") as mock_get:
            mock_get.side_effect = [
                {"items": [{"id": 1}], "totalSize": 2},
                {"items": [{"id": 2}], "totalSize": 2},
            ]
            result = client._paginate("endpoint", {}, "items", "totalSize")
            assert len(result) == 2
            assert mock_get.call_count == 2

    def test_empty_response(self, client):
        """Empty response returns empty list."""
        with patch.object(client, "get") as mock_get:
            mock_get.return_value = {}
            result = client._paginate("endpoint", {}, "items", "totalSize")
            assert result == []

    def test_partial_failure_mid_pagination(self, client):
        """If API fails mid-pagination, returns items collected so far."""
        with patch.object(client, "get") as mock_get:
            mock_get.side_effect = [
                {"items": [{"id": 1}], "totalSize": 3},
                {},
            ]
            result = client._paginate("endpoint", {}, "items", "totalSize")
            assert len(result) == 1


class TestListWorkflows:
    def test_filters_by_pipeline(self, client):
        """Workflows are filtered by pipeline name after pagination."""
        with patch.object(client, "_paginate") as mock_paginate:
            mock_paginate.return_value = [
                {"workflow": {"id": "1", "projectName": "nf-core/rnaseq", "repository": ""}},
                {"workflow": {"id": "2", "projectName": "nf-core/sarek", "repository": ""}},
            ]
            result = client.list_workflows("ws1", "2025-01-01", "2025-02-01", pipeline="nf-core/rnaseq")
            assert len(result) == 1
            assert result[0]["workflow"]["id"] == "1"

    def test_no_filter_returns_all(self, client):
        """Without filters, all paginated workflows are returned."""
        with patch.object(client, "_paginate") as mock_paginate:
            mock_paginate.return_value = [
                {"workflow": {"id": "1", "projectName": "nf-core/rnaseq", "repository": ""}},
                {"workflow": {"id": "2", "projectName": "nf-core/sarek", "repository": ""}},
            ]
            result = client.list_workflows("ws1", "2025-01-01", "2025-02-01")
            assert len(result) == 2


class TestWorkflowTasks:
    def test_returns_all_tasks(self, client):
        """workflow_tasks returns all paginated tasks."""
        with patch.object(client, "_paginate") as mock_paginate:
            mock_paginate.return_value = [{"task": {"id": 1}}, {"task": {"id": 2}}]
            result = client.workflow_tasks("wf1", "ws1")
            assert result["total"] == 2
            assert len(result["tasks"]) == 2
