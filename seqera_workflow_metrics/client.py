import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        try:
            logger.debug(f"Making GET request to {url} with params {params}")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            logger.debug(f"Response from {url}: {response.status_code}")
            return response.json()
        except requests.exceptions.RequestException as err:
            logger.error(f"Request failed for {url}: {err}")
            return {}

    def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any],
        items_key: str,
        total_key: str,
        max_per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Generic paginated GET. Returns all items across pages."""
        all_items: list[dict[str, Any]] = []
        offset = 0

        while True:
            page_params = {**params, "offset": offset, "max": max_per_page}
            resp = self.get(endpoint, page_params)
            if not resp:
                break

            items = resp.get(items_key, [])
            all_items.extend(items)

            total = resp.get(total_key, 0)
            if len(all_items) >= total or len(items) == 0:
                break

            offset += len(items)

        return all_items

    def organizations(self) -> dict[str, Any]:
        items = self._paginate("orgs", {}, "organizations", "totalSize")
        return {"organizations": items}

    def workspaces(self, org_id: str) -> dict[str, Any]:
        items = self._paginate(f"orgs/{org_id}/workspaces", {}, "workspaces", "totalSize")
        return {"workspaces": items}

    def _build_search_query(self, min_time: str, max_time: str, status: str | None = None) -> str:
        query = f"after:{min_time} before:{max_time}"
        if status:
            query += f" status:{status}"
        return query

    def _filter_workflows_by_criteria(
        self,
        workflows: list[dict[str, Any]],
        pipeline: str | None = None,
        repository: str | None = None,
    ) -> list[dict[str, Any]]:
        if not (pipeline or repository):
            return workflows
        return [
            wf
            for wf in workflows
            if (pipeline and wf.get("workflow", {}).get("projectName") == pipeline)
            or (repository and wf.get("workflow", {}).get("repository") == repository)
        ]

    def list_workflows(
        self,
        workspace_id: str,
        min_time: str,
        max_time: str,
        pipeline: str | None = None,
        repository: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        search_query = self._build_search_query(min_time, max_time, status)
        params = {"search": search_query, "workspaceId": workspace_id}

        all_workflows = self._paginate("workflow", params, "workflows", "totalSize")
        return self._filter_workflows_by_criteria(all_workflows, pipeline, repository)

    def workflow_details(self, workflow_id: str, workspace_id: str) -> dict[str, Any]:
        return self.get(f"workflow/{workflow_id}", {"workspaceId": workspace_id})

    def workflow_tasks(self, workflow_id: str, workspace_id: str) -> dict[str, Any]:
        params = {"workspaceId": workspace_id}
        all_tasks = self._paginate(f"workflow/{workflow_id}/tasks", params, "tasks", "total")
        return {"tasks": all_tasks, "total": len(all_tasks)}
