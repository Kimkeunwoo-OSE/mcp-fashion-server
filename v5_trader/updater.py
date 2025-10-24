"""CLI entry point for checking v5 Trader updates."""
from __future__ import annotations

from rich.console import Console

from v5_trader.core.updater.service import UpdateService


console = Console()


def main() -> None:
    service = UpdateService()
    release = service.latest_release()
    if release is None:
        console.print("[yellow]Could not reach GitHub or no releases available.[/yellow]")
        return
    console.print(f"[bold green]Latest Release:[/bold green] {release.tag_name}")
    console.print(f"URL: {release.html_url}")
    if release.body:
        console.print("\n" + release.body)


if __name__ == "__main__":
    main()
