"""Client for interacting with the price_monitor service."""

from __future__ import annotations

import logging
from typing import Dict, List

import requests

from .models import MonitorType

logger = logging.getLogger(__name__)


class MonitorClient:
    """HTTP client wrapper for the price_monitor API."""

    def __init__(self, base_url: str = "http://localhost:8888"):
        self.base_url = base_url.rstrip("/")

    def create_task(self, payload: Dict) -> Dict:
        url = f"{self.base_url}/api/monitor/create"
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error("Failed to create monitor task: %s", response.text)
            response.raise_for_status()
        return response.json()

    def delete_task(self, task_id: str) -> None:
        url = f"{self.base_url}/api/monitor/{task_id}"
        response = requests.delete(url, timeout=10)
        if response.status_code not in (200, 404):
            logger.error("Failed to delete monitor task %s: %s", task_id, response.text)
            response.raise_for_status()

    def sync_level_tasks(
        self,
        strategy_id: str,
        level_id: str,
        option_symbol: str,
        monitor_definitions: List[Dict],
        webhook_url: str,
    ) -> Dict[MonitorType, str]:
        """Create or refresh monitor tasks for a level.

        Args:
            strategy_id: parent strategy
            level_id: level id
            option_symbol: option symbol to monitor
            monitor_definitions: list of dicts {"monitor_type", "target_price"}
            webhook_url: callback URL

        Returns:
            Mapping of MonitorType to created task_id.
        """

        task_ids: Dict[MonitorType, str] = {}
        for definition in monitor_definitions:
            monitor_type = MonitorType(definition["monitor_type"])
            target_price = definition["target_price"]
            task_id = f"strategy-{strategy_id}-{level_id}-{monitor_type.value}".lower()

            payload = {
                "task_id": task_id,
                "strategy_id": strategy_id,
                "level_id": level_id,
                "monitor_type": monitor_type.value,
                "option_symbol": option_symbol,
                "target_price": target_price,
                "webhook_url": webhook_url,
                "metadata": definition.get("metadata", {}),
                "timeout_hours": definition.get("timeout_hours", 168),
            }

            self.create_task(payload)
            task_ids[monitor_type] = task_id

        return task_ids


monitor_client = MonitorClient()
