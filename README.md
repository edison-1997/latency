# Monitoreo de latencia Mikrotik

Este repositorio incluye un script para monitorear la latencia de un equipo Mikrotik y disparar alertas cuando la latencia supera **50ms durante 5 minutos continuos**.

## Requisitos

- Python 3.8+
- Comando `ping` disponible en el sistema

## Uso básico

```bash
python3 monitor_mikrotik_latency.py 192.168.88.1
```

Con esta ejecución se aplica:

- Umbral: `50ms`
- Duración continua para alerta: `300s` (5 min)
- Intervalo de muestreo: `1s`

## Enviar alertas por webhook

```bash
python3 monitor_mikrotik_latency.py 192.168.88.1 \
  --threshold-ms 50 \
  --duration-s 300 \
  --alert-webhook https://tu-endpoint/alertas
```

Payload JSON de alerta:

```json
{
  "event": "mikrotik_high_latency",
  "host": "192.168.88.1",
  "threshold_ms": 50,
  "duration_s": 300,
  "detected_at": "2026-01-01 10:00:00",
  "message": "ALERTA: latencia > 50ms por al menos 300s en 192.168.88.1"
}
```

## Parámetros útiles

- `--interval-s`: cada cuánto hacer ping.
- `--timeout-s`: timeout de cada ping.
- `--cooldown-s`: tiempo mínimo entre alertas repetidas.
- `--allow-packet-loss`: no rompe la ventana si hay timeout/pérdida de ping.

## Ejecución como servicio (ejemplo systemd)

```ini
[Unit]
Description=Monitoreo de latencia Mikrotik
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /ruta/monitor_mikrotik_latency.py 192.168.88.1 --threshold-ms 50 --duration-s 300 --alert-webhook https://tu-endpoint/alertas
Restart=always

[Install]
WantedBy=multi-user.target
```
