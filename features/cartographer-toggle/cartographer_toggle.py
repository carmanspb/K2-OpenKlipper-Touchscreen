"""Adapter for the standalone K2 Cartographer lifecycle; never edits printer files."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

BEGIN = "# BEGIN k2-openklipper-cartographer"
END = "# END k2-openklipper-cartographer"
IDLE = {"standby", "complete", "cancelled", "error"}


class Integration:
    def __init__(self, root=Path("/")):
        self.root = Path(root)
        self.repo = self.root / "mnt/UDISK/k2-openklipper-cartographer"
        self.control = self.root / "mnt/UDISK/k2-cartographer-control"
        self.addon = self.root / "mnt/UDISK/k2-cartographer"

    @staticmethod
    def read(path):
        return json.loads(path.read_text())

    def inspect(self):
        """Recognize only this add-on's complete, managed installation."""
        try:
            manifest = self.read(self.addon / "manifest.json")
            lifecycle = self.read(self.control / "lifecycle.json")
            # Recognize our managed installation, not a particular plugin fork
            # or release. The add-on owns compatibility with its dependencies.
            for name in ("k2ctl.py", "setup.py", "usb.py", "bridge.py", "firmware.py"):
                if not (self.repo / "scripts" / name).is_file():
                    return {"available": False}
            if not (self.repo / "plugin-lock.json").is_file():
                return {"available": False}
            override = Path(manifest["override"])
            stub = Path(manifest["stub"])
            if not override.is_absolute() or not stub.is_absolute():
                return {"available": False}
            loader = stub.read_bytes()
            if hashlib.sha256(loader).hexdigest() != manifest["stub_sha256"]:
                return {"available": False}
            vendor = self.addon / "vendor"
            if (
                str(vendor) not in loader.decode()
                or "from cartographer.extra import load_config" not in loader.decode()
            ):
                return {"available": False}
            if (
                "# Managed by k2-openklipper-cartographer" not in loader.decode()
                or not (vendor / "cartographer/extra.py").is_file()
            ):
                return {"available": False}
            settings = self.read(self.repo / "config/lifecycle.json")
            if (
                settings.get("hardware") != "cartographer-v3"
                or not settings.get("runtime_serial")
                or settings["runtime_serial"].startswith("REPLACE")
            ):
                return {"available": False}
            text = override.read_text()
            if text.count(BEGIN) != 1 or text.count(END) != 1:
                return {"available": False}
            block = text.split(BEGIN, 1)[1].split(END, 1)[0].strip()
            enabled = block == "[include cartographer-mesh.cfg]"
            if not enabled and block != "# Cartographer disabled":
                return {"available": False}
            pending = lifecycle.get("restart_pending") is True
            if lifecycle.get("enabled") is not enabled:
                return {"available": False}
            return {"available": True, "enabled": enabled, "restart_pending": pending}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return {"available": False}

    def apply(self, enabled, moonraker):
        if not self.inspect().get("available"):
            raise ValueError(
                "Compatible Cartographer installation is no longer available"
            )
        manifest = self.read(self.addon / "manifest.json")
        command = [
            str(self.root / "usr/share/klippy-env/bin/python"),
            str(self.repo / "scripts/k2ctl.py"),
            "enable" if enabled else "disable",
            "--apply",
            "--settings",
            str(self.repo / "config/lifecycle.json"),
            "--control-dir",
            str(self.control),
            "--addon-state",
            str(self.addon),
            "--config-dir",
            str(Path(manifest["override"]).parent),
            "--build",
            str(Path(manifest["stub"]).parents[2]),
            "--moonraker",
            moonraker,
        ]
        # The lifecycle utility owns the lock, USB service, include, saved
        # calibration and restart. Never duplicate its mutations or restart twice.
        result = subprocess.run(command, capture_output=True, text=True, timeout=110)
        if result.returncode:
            raise RuntimeError(
                (result.stderr or result.stdout or "Cartographer change failed")[
                    -1200:
                ].strip()
            )
        state = self.inspect()
        if (
            not state.get("available")
            or state.get("enabled") is not enabled
            or state.get("restart_pending")
        ):
            raise RuntimeError("Cartographer change could not be verified")
        return state


def blocked(status, connected, operations):
    if not connected or status.get("webhooks", {}).get("state") != "ready":
        return "Printer is not ready"
    if status.get("print_stats", {}).get("state") not in IDLE:
        return "Unavailable during printing or while print state is unknown"
    if operations:
        return "Wait for the current operation to finish"
    if status.get("idle_timeout", {}).get("state") == "Printing":
        return "Wait for printer movement to finish"
    motor = status.get("k2_motor_bus", {})
    if motor and not motor.get("motors_ready", False):
        return "Wait for motor initialization to finish"
    cfs = status.get("k2_cfs", {})
    if cfs.get("change_pending") or (cfs.get("filament_activity") or {}).get(
        "action"
    ) in ("load", "unload"):
        return "Wait for the filament change to finish"
    return ""


def verify_runtime(mr, enabled, *, timeout=25):
    """Wait for the new host, configuration and native initialization, bounded."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status = mr.query()
            settings = mr.settings()
            motor = status.get("k2_motor_bus", {})
            if (
                status.get("webhooks", {}).get("state") == "ready"
                and (not motor or motor.get("motors_ready") is True)
                and ("cartographer" in settings) is enabled
                and ("mcu cartographer" in settings) is enabled
            ):
                return
        except (OSError, RuntimeError, KeyError, ValueError):
            pass
        time.sleep(0.5)
    raise RuntimeError(
        "Klipper did not return with the requested Cartographer configuration. Check printer logs before retrying."
    )
