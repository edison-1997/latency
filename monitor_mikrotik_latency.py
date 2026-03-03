#!/usr/bin/env python3
"""Monitorea latencia de un Mikrotik y dispara alertas por umbral sostenido."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Optional

PING_RE = re.compile(r"time[=<]([0-9]+(?:\.[0-9]+)?)\s*ms", re.IGNORECASE)


@dataclass
class Sample:
    timestamp: float
    latency_ms: Optional[float]


def ping_once(host: str, timeout_s: float) -> Optional[float]:
    """Ejecuta un solo ping y retorna latencia en ms o None si falla."""
    is_windows = platform.system().lower().startswith("win")
    timeout_ms = str(int(timeout_s * 1000))

    if is_windows:
        cmd = ["ping", "-n", "1", "-w", timeout_ms, host]
    else:
        # Linux/macOS: -W timeout en segundos en Linux, -t ttl en mac. Usamos timeout externo.
        cmd = ["ping", "-c", "1", host]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1.0, timeout_s + 1.0),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None

    output = f"{completed.stdout}\n{completed.stderr}"
    match = PING_RE.search(output)
    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def send_webhook(url: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def sustained_over_threshold(
    window: Deque[Sample],
    threshold_ms: float,
    duration_s: int,
    allow_packet_loss: bool,
) -> bool:
    if not window:
        return False

    start = window[0].timestamp
    end = window[-1].timestamp
    if (end - start) < duration_s:
        return False

    for sample in window:
        if sample.latency_ms is None:
            if allow_packet_loss:
                continue
            return False
        if sample.latency_ms <= threshold_ms:
            return False
    return True


def format_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Monitorea latencia de un equipo Mikrotik y alerta cuando excede un umbral "
            "durante un tiempo continuo."
        )
    )
    parser.add_argument("host", help="IP o hostname del Mikrotik")
    parser.add_argument(
        "--threshold-ms",
        type=float,
        default=50.0,
        help="Umbral de latencia en ms (default: 50)",
    )
    parser.add_argument(
        "--duration-s",
        type=int,
        default=300,
        help="Duración continua sobre umbral para alertar, en segundos (default: 300 = 5 min)",
    )
    parser.add_argument(
        "--interval-s",
        type=float,
        default=1.0,
        help="Intervalo entre pings en segundos (default: 1)",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=1.0,
        help="Timeout de cada ping en segundos (default: 1)",
    )
    parser.add_argument(
        "--alert-webhook",
        help="URL webhook para enviar alerta en JSON (opcional)",
    )
    parser.add_argument(
        "--cooldown-s",
        type=int,
        default=600,
        help="Tiempo mínimo entre alertas repetidas (default: 600)",
    )
    parser.add_argument(
        "--allow-packet-loss",
        action="store_true",
        help="Si se activa, pérdida de ping no rompe la ventana de latencia sostenida",
    )
    args = parser.parse_args()

    print(
        f"Iniciando monitoreo host={args.host} threshold={args.threshold_ms}ms "
        f"duration={args.duration_s}s interval={args.interval_s}s"
    )

    samples: Deque[Sample] = deque()
    last_alert_ts = 0.0
    max_window_age = args.duration_s + max(5, int(args.interval_s * 2))

    while True:
        now = time.time()
        latency = ping_once(args.host, args.timeout_s)
        samples.append(Sample(timestamp=now, latency_ms=latency))

        while samples and (now - samples[0].timestamp) > max_window_age:
            samples.popleft()

        latency_text = "timeout" if latency is None else f"{latency:.2f}ms"
        print(f"[{format_ts(now)}] ping={latency_text}")

        if sustained_over_threshold(
            samples,
            threshold_ms=args.threshold_ms,
            duration_s=args.duration_s,
            allow_packet_loss=args.allow_packet_loss,
        ):
            if (now - last_alert_ts) >= args.cooldown_s:
                message = (
                    f"ALERTA: latencia > {args.threshold_ms}ms por al menos "
                    f"{args.duration_s}s en {args.host}"
                )
                print(f"[{format_ts(now)}] {message}")
                payload = {
                    "event": "mikrotik_high_latency",
                    "host": args.host,
                    "threshold_ms": args.threshold_ms,
                    "duration_s": args.duration_s,
                    "detected_at": format_ts(now),
                    "message": message,
                }
                if args.alert_webhook:
                    try:
                        send_webhook(args.alert_webhook, payload)
                        print(f"[{format_ts(now)}] Alerta enviada a webhook")
                    except urllib.error.URLError as exc:
                        print(f"[{format_ts(now)}] Error enviando webhook: {exc}", file=sys.stderr)
                last_alert_ts = now

        time.sleep(args.interval_s)


if __name__ == "__main__":
    raise SystemExit(main())
