"""Update checker that queries GitHub releases."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests


GITHUB_REPO = "your-org/v5-trader"


@dataclass
class ReleaseInfo:
    tag_name: str
    html_url: str
    body: str


class UpdateService:
    """Fetch the latest release information from GitHub."""

    def __init__(self, repo: str = GITHUB_REPO) -> None:
        self.repo = repo

    def latest_release(self) -> Optional[ReleaseInfo]:
        url = f"https://api.github.com/repos/{self.repo}/releases/latest"
        response = requests.get(url, timeout=5.0)
        if response.status_code != 200:
            return None
        data = response.json()
        return ReleaseInfo(tag_name=data.get("tag_name", ""), html_url=data.get("html_url", ""), body=data.get("body", ""))
