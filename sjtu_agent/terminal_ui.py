from __future__ import annotations

import json
import sys
from typing import Any, Iterable

try:
    from rich.console import Console
    from rich.json import JSON
    from rich.markdown import Markdown
    from rich.rule import Rule
except Exception:
    Console = None  # type: ignore[assignment]
    JSON = None  # type: ignore[assignment]
    Markdown = None  # type: ignore[assignment]
    Rule = None  # type: ignore[assignment]


_CONSOLE = Console(highlight=False, soft_wrap=True) if Console is not None else None


def _use_rich() -> bool:
    return _CONSOLE is not None and sys.stdout.isatty()


def print_rule(title: str) -> None:
    if _use_rich():
        _CONSOLE.print(Rule(f"[bold cyan]{title}[/bold cyan]"))
        return
    print(f"\n== {title} ==")


def print_status(label: str, ok: bool, detail: str = "") -> None:
    if _use_rich():
        icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        suffix = f" [dim]- {detail}[/dim]" if detail else ""
        _CONSOLE.print(f"{icon} [bold]{label}[/bold]{suffix}")
        return
    status = "OK" if ok else "MISSING"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")


def print_key_value(label: str, value: Any) -> None:
    text = str(value)
    if _use_rich():
        _CONSOLE.print(f"[bold]{label}:[/bold] {text}")
        return
    print(f"{label}: {text}")


def print_bullets(items: Iterable[str], title: str | None = None) -> None:
    entries = [item for item in items if item]
    if not entries:
        return
    if title:
        print_rule(title)
    for item in entries:
        if _use_rich():
            _CONSOLE.print(f"[cyan]•[/cyan] {item}")
        else:
            print(f"- {item}")


def print_json(data: Any) -> None:
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
    if _use_rich():
        _CONSOLE.print(JSON(text))
        return
    print(text)


def print_markdown_message(label: str, message: str, style: str = "cyan") -> None:
    text = (message or "").strip()
    if not text:
        return
    if _use_rich():
        _CONSOLE.print()
        _CONSOLE.print(f"[bold {style}]{label}[/bold {style}]")
        _CONSOLE.print(Markdown(text))
        _CONSOLE.print()
        return
    print(f"\n{label}: {text}\n")