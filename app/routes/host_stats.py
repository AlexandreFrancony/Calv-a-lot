"""Host system stats for remote monitoring (used by admin dashboard)."""

import os
import subprocess

from flask import Blueprint, jsonify

host_stats_bp = Blueprint("host_stats", __name__)


@host_stats_bp.route("/api/host-stats")
def host_stats():
    """System stats from /proc/ — CPU, RAM, disk, temp, uptime."""
    data = {}

    # CPU (load average / cores)
    try:
        with open("/proc/loadavg") as f:
            load1 = float(f.read().split()[0])
        cores = os.cpu_count() or 1
        data["cpu"] = {"percent": round(min(load1 / cores * 100, 100), 1)}
    except Exception:
        data["cpu"] = {"percent": 0}

    # Memory
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1]) * 1024
            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            data["memory"] = {
                "total": total,
                "used": total - available,
                "available": available,
            }
    except Exception:
        data["memory"] = {"total": 0, "used": 0, "available": 0}

    # Disk
    try:
        result = subprocess.run(
            ["df", "-B1", "/"], capture_output=True, text=True, timeout=5
        )
        parts = result.stdout.strip().split("\n")[-1].split()
        data["disk"] = {"total": int(parts[1]), "used": int(parts[2])}
    except Exception:
        data["disk"] = {"total": 0, "used": 0}

    # Temperature
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            data["temperature"] = round(int(f.read().strip()) / 1000, 1)
    except Exception:
        data["temperature"] = None

    # Uptime
    try:
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        days, rem = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        mins = rem // 60
        parts = []
        if days:
            parts.append(f"{days}j")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        data["uptime"] = " ".join(parts)
    except Exception:
        data["uptime"] = "?"

    return jsonify(data)
