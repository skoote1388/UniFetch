#!/usr/bin/env python3
"""
UniFetch - a small, dependency-free system information tool.

Works best on Linux, macOS, and the BSD family. Missing information is
silently omitted so the program remains useful on minimal installations.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path


VERSION = "0.2.0"

LOGOS = {
    "arch": [
        "       /\\",
        "      /  \\",
        "     /\\   \\",
        "    /      \\",
        "   /   ,,   \\",
        "  /   |  |  -\\",
        " /_-''    ''-_\\",
    ],
    "ubuntu": [
        "         _",
        "     ---(_)",
        " _/  ---  \\",
        "(_) |   |",
        "  \\  --- _/",
        "     ---(_)",
    ],
    "debian": [
        "       _____",
        "      /  __ \\",
        "     |  /    |",
        "     |  \\___-",
        "      -_",
        "        --_",
    ],
    "fedora": [
        "      _____",
        "     / ____|",
        "    | |  __",
        "    | | |_ |",
        "    | |__| |",
        "     \\_____/",
    ],
    "macos": [
        "       .:.",
        "      .:::.",
        "     .:::::.",
        "    .:::::::.",
        "   .:::::::::.",
        "      |   |",
    ],
    "freebsd": [
        "       ____",
        "     .'    '.",
        "    /  .--.  \\",
        "   |  /    \\  |",
        "   |  \\    /  |",
        "    \\  '--'  /",
        "     '.____.'",
    ],
    "generic": [
        "       .--.",
        "      |o_o |",
        "      |:_/ |",
        "     //   \\ \\",
        "    (|     | )",
        "   /'\\_   _/`\\",
        "   \\___)=(___/",
    ],
}

ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
    "blue": "\033[34m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
}


def run(command: list[str], timeout: float = 2.0) -> str:
    """Run a command safely; return an empty string if unavailable."""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def read_text(path: str) -> str:
    try:
        return Path(path).read_text(errors="replace").strip()
    except OSError:
        return ""


def detect_os() -> tuple[str, str]:
    system = platform.system()
    if system == "Linux":
        data = {}
        for line in read_text("/etc/os-release").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data[key] = value.strip().strip('"')
        name = data.get("PRETTY_NAME") or data.get("NAME") or "Linux"
        ident = data.get("ID", "linux").lower()
        return name, ident
    if system == "Darwin":
        version = platform.mac_ver()[0]
        return (f"macOS {version}" if version else "macOS"), "macos"
    if system in {"FreeBSD", "OpenBSD", "NetBSD", "DragonFly"}:
        return f"{system} {platform.release()}", system.lower()
    return f"{system} {platform.release()}".strip(), system.lower()


def detect_cpu() -> str:
    system = platform.system()
    if system == "Linux":
        for line in read_text("/proc/cpuinfo").splitlines():
            if line.lower().startswith(("model name", "hardware")) and ":" in line:
                return line.split(":", 1)[1].strip()
    if system == "Darwin":
        value = run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if value:
            return value
        value = run(["sysctl", "-n", "hw.model"])
        if value:
            return value
    for key in ("hw.model", "hw.machine"):
        value = run(["sysctl", "-n", key])
        if value and value.lower() not in {"x86_64", "amd64", "arm64"}:
            return value
    return platform.processor() or platform.machine() or "Unknown"


def detect_gpu() -> str:
    # NVIDIA's own utility gives a more useful name when installed.
    value = run([
        "nvidia-smi", "--query-gpu=name", "--format=csv,noheader"
    ])
    if value:
        return value.splitlines()[0].strip()

    if platform.system() == "Linux":
        output = run(["lspci"])
        for line in output.splitlines():
            if re.search(r"VGA compatible controller|3D controller|Display controller", line, re.I):
                return line.split(": ", 1)[-1].strip()
    if platform.system() == "Darwin":
        output = run(["system_profiler", "SPDisplaysDataType"], timeout=5)
        for line in output.splitlines():
            if "Chipset Model:" in line:
                return line.split(":", 1)[1].strip()
    return ""


def memory_info() -> str:
    system = platform.system()
    if system == "Linux":
        values = {}
        for line in read_text("/proc/meminfo").splitlines():
            match = re.match(r"^(MemTotal|MemAvailable):\s+(\d+)", line)
            if match:
                values[match.group(1)] = int(match.group(2)) * 1024
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if total and available is not None:
            used = total - available
            return f"{format_bytes(used)} / {format_bytes(total)}"
    elif system == "Darwin":
        total_text = run(["sysctl", "-n", "hw.memsize"])
        vm = run(["vm_stat"])
        try:
            total = int(total_text)
            page_size_match = re.search(r"page size of (\d+) bytes", vm)
            page_size = int(page_size_match.group(1)) if page_size_match else 4096
            pages = {}
            for line in vm.splitlines():
                match = re.match(r"([^:]+):\s+([\d.]+)", line)
                if match:
                    pages[match.group(1).strip()] = int(float(match.group(2)))
            free_pages = pages.get("Pages free", 0) + pages.get("Pages inactive", 0)
            used = max(0, total - free_pages * page_size)
            return f"{format_bytes(used)} / {format_bytes(total)}"
        except (ValueError, TypeError):
            pass
    else:
        total_text = run(["sysctl", "-n", "hw.physmem"])
        if not total_text:
            total_text = run(["sysctl", "-n", "hw.physmem64"])
        try:
            total = int(total_text)
            return f"{format_bytes(total)} total"
        except ValueError:
            pass
    return ""


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TiB"


def detect_uptime() -> str:
    if platform.system() == "Linux":
        raw = read_text("/proc/uptime").split()
        if raw:
            seconds = int(float(raw[0]))
        else:
            return ""
    else:
        boot = run(["sysctl", "-n", "kern.boottime"])
        match = re.search(r"sec\s*=\s*(\d+)", boot)
        if not match:
            return ""
        seconds = max(0, int(__import__("time").time()) - int(match.group(1)))

    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def detect_desktop() -> str:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION")
    if desktop:
        return desktop.replace(":", " / ")
    if os.environ.get("KDE_FULL_SESSION"):
        return "KDE Plasma"
    if os.environ.get("MATE_DESKTOP_SESSION_ID"):
        return "MATE"
    if os.environ.get("GNOME_DESKTOP_SESSION_ID"):
        return "GNOME"
    return ""


def detect_window_manager() -> str:
    if os.environ.get("WAYLAND_DISPLAY"):
        return "Wayland"
    if os.environ.get("DISPLAY"):
        value = run(["xprop", "-root", "_NET_SUPPORTING_WM_CHECK"])
        if value:
            window_id = re.search(r"window id # (0x[0-9a-fA-F]+)", value)
            if window_id:
                name = run(["xprop", "-id", window_id.group(1), "_NET_WM_NAME"])
                match = re.search(r' = "([^"]+)"', name)
                if match:
                    return match.group(1)
        return "X11"
    return ""


def detect_packages(os_id: str) -> str:
    commands = {
        "arch": ["pacman", "-Qq"],
        "endeavouros": ["pacman", "-Qq"],
        "cachyos": ["pacman", "-Qq"],
        "manjaro": ["pacman", "-Qq"],
        "debian": ["dpkg-query", "-f", ".\\n", "-W"],
        "ubuntu": ["dpkg-query", "-f", ".\\n", "-W"],
        "linuxmint": ["dpkg-query", "-f", ".\\n", "-W"],
        "fedora": ["rpm", "-qa"],
        "opensuse": ["rpm", "-qa"],
        "alpine": ["apk", "info"],
        "void": ["xbps-query", "-l"],
        "freebsd": ["pkg", "info"],
        "openbsd": ["pkg_info"],
        "netbsd": ["pkg_info"],
    }
    candidates = commands.get(os_id, [])
    if not candidates and platform.system() == "Linux":
        candidates = [
            ["pacman", "-Qq"], ["dpkg-query", "-f", ".\\n", "-W"],
            ["rpm", "-qa"], ["apk", "info"], ["xbps-query", "-l"]
        ]
    if candidates and isinstance(candidates[0], str):
        candidates = [candidates]
    for command in candidates:
        output = run(command, timeout=5)
        if output:
            return str(len(output.splitlines()))
    return ""


def detect_disk() -> str:
    try:
        usage = shutil.disk_usage("/")
        return f"{format_bytes(usage.used)} / {format_bytes(usage.total)}"
    except OSError:
        return ""


def detect_terminal() -> str:
    term_program = os.environ.get("TERM_PROGRAM")
    if term_program:
        return term_program
    term = os.environ.get("TERM", "")
    if term and term != "dumb":
        return term
    return ""


def detect_logo(os_id: str) -> list[str]:
    if os_id in {"arch", "endeavouros", "cachyos", "manjaro"}:
        return LOGOS["arch"]
    if os_id in {"ubuntu", "linuxmint", "pop", "elementary"}:
        return LOGOS["ubuntu"]
    if os_id in {"debian"}:
        return LOGOS["debian"]
    if os_id in {"fedora", "rhel", "centos"}:
        return LOGOS["fedora"]
    if os_id == "macos":
        return LOGOS["macos"]
    if os_id in {"freebsd", "openbsd", "netbsd", "dragonfly"}:
        return LOGOS["freebsd"]
    return LOGOS["generic"]


def collect() -> tuple[dict[str, str], str, list[str]]:
    os_name, os_id = detect_os()
    info = {
        "User": f"{getpass.getuser()}@{socket.gethostname()}",
        "OS": os_name,
        "Host": platform.machine(),
        "Kernel": f"{platform.system()} {platform.release()}",
        "Uptime": detect_uptime(),
        "Packages": detect_packages(os_id),
        "Shell": Path(os.environ.get("SHELL", "")).name if os.environ.get("SHELL") else "",
        "Terminal": detect_terminal(),
        "Desktop": detect_desktop(),
        "Window Manager": detect_window_manager(),
        "CPU": detect_cpu(),
        "GPU": detect_gpu(),
        "Memory": memory_info(),
        "Disk (/):": detect_disk(),
        "Python": platform.python_version(),
    }
    info = {key: value for key, value in info.items() if value}
    return info, os_id, detect_logo(os_id)


def render(info: dict[str, str], logo: list[str], color: bool = True) -> str:
    colors = ANSI if color else {key: "" for key in ANSI}
    label_color = colors["cyan"]
    logo_color = colors["blue"]
    reset = colors["reset"]
    title_color = colors["bold"] + colors["green"]

    lines = [
        f"{title_color}{info.get('User', 'UniFetch')}{reset}",
        f"{colors['yellow']}{'─' * 28}{reset}",
    ]
    for key, value in info.items():
        if key == "User":
            continue
        lines.append(f"{label_color}{key:<15}{reset} {value}")

    width = max((len(line) for line in logo), default=0)
    output = []
    total = max(len(logo), len(lines))
    for index in range(total):
        left = logo[index] if index < len(logo) else ""
        right = lines[index] if index < len(lines) else ""
        output.append(f"{logo_color}{left:<{width}}{reset}   {right}")
    return "\n".join(output)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A lightweight, cross-platform system information tool."
    )
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--json", action="store_true", help="Print system information as JSON")
    parser.add_argument("--logo", action="store_true", help="Print only the detected ASCII logo")
    parser.add_argument("--version", action="version", version=f"UniFetch {VERSION}")
    args = parser.parse_args()

    info, _os_id, logo = collect()
    if args.logo:
        print("\n".join(logo))
    elif args.json:
        print(json.dumps(info, indent=2))
    else:
        use_color = not args.no_color and sys.stdout.isatty() and "NO_COLOR" not in os.environ
        print(render(info, logo, use_color))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
