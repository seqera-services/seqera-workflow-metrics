from unittest.mock import patch

import pytest

from seqera_workflow_metrics.client import APIClient
from seqera_workflow_metrics.studios.models import CheckpointRecord, StudioRecord


@pytest.fixture
def client():
    return APIClient("https://api.example.com", "tok")


class TestListStudios:
    def test_returns_parsed_studio_records(self, client):
        raw_studio = {
            "sessionId": "s1", "name": "my-studio",
            "user": {"userName": "alice"},
            "configuration": {"cpu": 4, "gpu": 0, "memory": 0},
            "computeEnv": {"id": "ce-1"},
            "statusInfo": {"status": "stopped"},
            "dateCreated": "2026-08-01T10:00:00Z",
        }
        with patch.object(client, "_paginate", return_value=[raw_studio]):
            studios = client.list_studios("ws123")
        assert len(studios) == 1
        assert isinstance(studios[0], StudioRecord)
        assert studios[0].session_id == "s1"

    def test_passes_workspace_id_as_param(self, client):
        with patch.object(client, "_paginate", return_value=[]) as mock_pag:
            client.list_studios("ws456")
        call_params = mock_pag.call_args[0][1]
        assert call_params["workspaceId"] == "ws456"

    def test_empty_workspace_returns_empty_list(self, client):
        with patch.object(client, "_paginate", return_value=[]):
            assert client.list_studios("ws123") == []


class TestStudioCheckpoints:
    def test_returns_parsed_checkpoint_records(self, client):
        raw = [
            {"id": 1, "dateCreated": "2026-08-01T10:00:00Z",
             "dateSaved": "2026-08-01T12:00:00Z", "status": "finalized"},
        ]
        with patch.object(client, "_paginate", return_value=raw):
            cps = client.studio_checkpoints("s1", "ws1")
        assert len(cps) == 1
        assert isinstance(cps[0], CheckpointRecord)
        assert cps[0].checkpoint_id == 1

    def test_no_checkpoints_returns_empty(self, client):
        with patch.object(client, "_paginate", return_value=[]):
            cps = client.studio_checkpoints("s1", "ws1")
        assert cps == []

    def test_api_failure_returns_empty(self, client):
        with patch.object(client, "_paginate", return_value=[]):
            cps = client.studio_checkpoints("s1", "ws1")
        assert cps == []
