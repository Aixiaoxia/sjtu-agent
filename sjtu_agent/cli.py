from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

from sjtu_agent import __version__
from sjtu_agent.launchd import DEFAULT_LAUNCH_AGENTS_DIR, available_service_names, install_launch_agents
from sjtu_agent.paths import describe_runtime_paths
from sjtu_agent.setup_wizard import register_setup_parser
from sjtu_agent.terminal_ui import print_json


def _run_module(module_name: str, script_args: list[str] | None = None) -> int:
    old_argv = sys.argv[:]
    sys.argv = [module_name, *(script_args or [])]
    try:
        runpy.run_module(module_name, run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 0
    finally:
        sys.argv = old_argv


def _cmd_doctor(_: argparse.Namespace) -> int:
    import agent

    payload = {
        "version": __version__,
        "paths": describe_runtime_paths(),
        "setup": agent.tool_check_setup(),
    }
    print_json(payload)
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    return _run_module("agent", args.script_args)


def _cmd_setup_config(args: argparse.Namespace) -> int:
    return _run_module("setup_config", args.script_args)


def _cmd_login(args: argparse.Namespace) -> int:
    return _run_module("login", args.script_args)


def _cmd_ddl(args: argparse.Namespace) -> int:
    return _run_module("ddl_checker", args.script_args)


def _cmd_daily_report(args: argparse.Namespace) -> int:
    return _run_module("daily_report", args.script_args)


def _cmd_telegram_bot(args: argparse.Namespace) -> int:
    return _run_module("telegram_bot", args.script_args)


def _cmd_remind_check(args: argparse.Namespace) -> int:
    return _run_module("remind_check", args.script_args)


def _cmd_mcp(args: argparse.Namespace) -> int:
    return _run_module("mcp_server", args.script_args)


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("time must be in HH:MM format") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise argparse.ArgumentTypeError("time must be in HH:MM format")
    return hour, minute


def _cmd_install_daemons(args: argparse.Namespace) -> int:
    try:
        payload = install_launch_agents(
            output_dir=Path(args.output_dir),
            service_names=tuple(args.services) if args.services else None,
            python_executable=Path(args.python_executable),
            daily_report_time=args.daily_report_time,
            remind_interval=args.remind_interval,
            telegram_throttle=args.telegram_throttle,
            load=not args.write_only,
        )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print_json(payload)
    return 0


def _add_passthrough_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
    handler,
) -> None:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("script_args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    parser.set_defaults(func=handler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sjtu-agent", description="Deployable CLI for SJTU Agent.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    register_setup_parser(subparsers, _parse_hhmm)

    _add_passthrough_parser(subparsers, "chat", "start interactive chat mode", _cmd_chat)
    _add_passthrough_parser(subparsers, "setup-config", "build config.json from browser cookies", _cmd_setup_config)
    _add_passthrough_parser(subparsers, "login", "refresh platform cookies with Playwright", _cmd_login)
    _add_passthrough_parser(subparsers, "ddl", "run the DDL checker report", _cmd_ddl)
    _add_passthrough_parser(subparsers, "daily-report", "generate or send the daily report", _cmd_daily_report)
    _add_passthrough_parser(subparsers, "telegram-bot", "start the Telegram bot", _cmd_telegram_bot)
    _add_passthrough_parser(subparsers, "remind-check", "run the reminder daemon once", _cmd_remind_check)
    _add_passthrough_parser(subparsers, "mcp", "start the MCP server", _cmd_mcp)

    install_daemons = subparsers.add_parser(
        "install-daemons",
        help="generate launchd plists and load them into the current macOS user session",
    )
    install_daemons.add_argument(
        "--output-dir",
        default=str(DEFAULT_LAUNCH_AGENTS_DIR),
        help="directory where plist files will be written",
    )
    install_daemons.add_argument(
        "--write-only",
        action="store_true",
        help="only write plist files; do not call launchctl",
    )
    install_daemons.add_argument(
        "--python-executable",
        default=sys.executable,
        help="python executable that launchd should use",
    )
    install_daemons.add_argument(
        "--services",
        nargs="+",
        choices=available_service_names(),
        help="subset of launchd services to generate",
    )
    install_daemons.add_argument(
        "--daily-report-time",
        type=_parse_hhmm,
        default=(22, 0),
        help="daily report schedule in HH:MM, default 22:00",
    )
    install_daemons.add_argument(
        "--remind-interval",
        type=int,
        default=60,
        help="reminder daemon interval in seconds, default 60",
    )
    install_daemons.add_argument(
        "--telegram-throttle",
        type=int,
        default=10,
        help="launchd throttle interval for telegram bot restarts, default 10",
    )
    install_daemons.set_defaults(func=_cmd_install_daemons)

    doctor = subparsers.add_parser("doctor", help="print runtime paths and setup status")
    doctor.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        return _cmd_chat(argparse.Namespace(script_args=[]))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())