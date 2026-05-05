from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from sjtu_agent.paths import DATA_DIR, LOG_DIR

DEFAULT_DAILY_REPORT_TIME = (22, 0)
DEFAULT_REMIND_INTERVAL = 60
DEFAULT_TELEGRAM_THROTTLE = 10
DEFAULT_LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


@dataclass(frozen=True)
class LaunchAgentSpec:
    name: str
    label: str
    subcommand: str
    log_path: Path
    run_at_load: bool
    start_interval: int | None = None
    start_calendar_interval: dict[str, int] | None = None
    keep_alive: bool | None = None
    throttle_interval: int | None = None

    @property
    def plist_name(self) -> str:
        return f"{self.label}.plist"


def available_service_names() -> tuple[str, ...]:
    return ("daily-report", "remind-check", "telegram-bot")


def build_launch_agent_specs(
    daily_report_time: tuple[int, int] = DEFAULT_DAILY_REPORT_TIME,
    remind_interval: int = DEFAULT_REMIND_INTERVAL,
    telegram_throttle: int = DEFAULT_TELEGRAM_THROTTLE,
) -> tuple[LaunchAgentSpec, ...]:
    hour, minute = daily_report_time
    return (
        LaunchAgentSpec(
            name="daily-report",
            label="com.sjtu.daily-report",
            subcommand="daily-report",
            log_path=LOG_DIR / "daily_report.launchd.log",
            run_at_load=False,
            start_calendar_interval={"Hour": hour, "Minute": minute},
        ),
        LaunchAgentSpec(
            name="remind-check",
            label="com.sjtu.remind",
            subcommand="remind-check",
            log_path=LOG_DIR / "remind_check.launchd.log",
            run_at_load=True,
            start_interval=remind_interval,
            keep_alive=False,
        ),
        LaunchAgentSpec(
            name="telegram-bot",
            label="com.sjtu.telegram-bot",
            subcommand="telegram-bot",
            log_path=LOG_DIR / "telegram_bot.launchd.log",
            run_at_load=True,
            keep_alive=True,
            throttle_interval=telegram_throttle,
        ),
    )


def _build_plist_payload(spec: LaunchAgentSpec, python_executable: Path) -> dict[str, object]:
    payload: dict[str, object] = {
        "Label": spec.label,
        "ProgramArguments": [str(python_executable), "-m", "sjtu_agent", spec.subcommand],
        "RunAtLoad": spec.run_at_load,
        "StandardOutPath": str(spec.log_path),
        "StandardErrorPath": str(spec.log_path),
        "WorkingDirectory": str(DATA_DIR),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
    }
    if spec.start_interval is not None:
        payload["StartInterval"] = spec.start_interval
    if spec.start_calendar_interval is not None:
        payload["StartCalendarInterval"] = spec.start_calendar_interval
    if spec.keep_alive is not None:
        payload["KeepAlive"] = spec.keep_alive
    if spec.throttle_interval is not None:
        payload["ThrottleInterval"] = spec.throttle_interval
    return payload


def write_launch_agent_plists(
    output_dir: Path = DEFAULT_LAUNCH_AGENTS_DIR,
    service_names: tuple[str, ...] | None = None,
    python_executable: Path | None = None,
    daily_report_time: tuple[int, int] = DEFAULT_DAILY_REPORT_TIME,
    remind_interval: int = DEFAULT_REMIND_INTERVAL,
    telegram_throttle: int = DEFAULT_TELEGRAM_THROTTLE,
) -> list[dict[str, object]]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    python_executable = Path(os.path.abspath(os.fspath(python_executable or sys.executable))).expanduser()
    selected_names = set(service_names or available_service_names())
    specs = [
        spec
        for spec in build_launch_agent_specs(
            daily_report_time=daily_report_time,
            remind_interval=remind_interval,
            telegram_throttle=telegram_throttle,
        )
        if spec.name in selected_names
    ]
    if not specs:
        raise ValueError("No launchd services selected.")

    written: list[dict[str, object]] = []
    for spec in specs:
        plist_path = output_dir / spec.plist_name
        payload = _build_plist_payload(spec, python_executable)
        with plist_path.open("wb") as f:
            plistlib.dump(payload, f, sort_keys=False)
        written.append(
            {
                "name": spec.name,
                "label": spec.label,
                "plist_path": str(plist_path),
                "log_path": str(spec.log_path),
                "command": payload["ProgramArguments"],
                "run_at_load": spec.run_at_load,
            }
        )
    return written


def _launchctl_domains() -> tuple[str, ...]:
    uid = os.getuid()
    return (f"gui/{uid}", f"user/{uid}")


def _bootout_if_present(domain: str, label: str, plist_path: Path) -> None:
    subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], capture_output=True, text=True)
    subprocess.run(["launchctl", "bootout", domain, str(plist_path)], capture_output=True, text=True)


def load_launch_agent(plist_path: Path, label: str) -> str:
    errors: list[str] = []
    for domain in _launchctl_domains():
        _bootout_if_present(domain, label, plist_path)
        result = subprocess.run(
            ["launchctl", "bootstrap", domain, str(plist_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return domain
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        message = stderr or stdout or f"exit code {result.returncode}"
        errors.append(f"{domain}: {message}")
    raise RuntimeError("; ".join(errors))


def install_launch_agents(
    output_dir: Path = DEFAULT_LAUNCH_AGENTS_DIR,
    service_names: tuple[str, ...] | None = None,
    python_executable: Path | None = None,
    daily_report_time: tuple[int, int] = DEFAULT_DAILY_REPORT_TIME,
    remind_interval: int = DEFAULT_REMIND_INTERVAL,
    telegram_throttle: int = DEFAULT_TELEGRAM_THROTTLE,
    load: bool = True,
) -> dict[str, object]:
    written = write_launch_agent_plists(
        output_dir=output_dir,
        service_names=service_names,
        python_executable=python_executable,
        daily_report_time=daily_report_time,
        remind_interval=remind_interval,
        telegram_throttle=telegram_throttle,
    )
    load_results: list[dict[str, object]] = []
    if load:
        if sys.platform != "darwin":
            raise RuntimeError("launchd installation is only supported on macOS.")
        for item in written:
            plist_path = Path(str(item["plist_path"]))
            domain = load_launch_agent(plist_path, str(item["label"]))
            load_results.append({"label": item["label"], "domain": domain})

    return {
        "output_dir": str(output_dir.expanduser().resolve()),
        "working_directory": str(DATA_DIR),
        "python_executable": str(Path(os.path.abspath(os.fspath(python_executable or sys.executable))).expanduser()),
        "load_requested": load,
        "services": written,
        "load_results": load_results,
    }