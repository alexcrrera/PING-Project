# Prototype telemetry protocol

The rover's actual firmware protocol has not been supplied. This receive-only
adapter demonstrates USB telemetry at **57600 baud**, 8 data bits, no parity,
1 stop bit. It does not implement rover control, traction optimization, or
transmit commands. Verify the firmware format before using real readings.

The prototype wire format is one UTF-8 JSON object per newline (`\n`, optionally
preceded by `\r`), at approximately 10 Hz. Each core field below is required. Wheel
arrays are optional or `null`, which means unknown. Order is always front-left,
front-right, rear-left, rear-right. Extra keys are ignored. The host stamps
`received_at` with its monotonic clock; device timestamps do not control freshness.

```json
{"schema":"ping.telemetry.v1","battery_voltage":24.4,"battery_percent":84,"speed_mps":0.65,"heading_deg":127,"pitch_deg":1.2,"roll_deg":-0.6,"motor_temp_c":36.2,"signal_rssi_dbm":-63,"latency_ms":28,"distance_m":12.4,"wheel_rpm":[45,45,46,47],"wheel_slip":[0.02,0.02,0.03,0.05],"motor_current_a":[3.2,3.2,3.3,3.4]}
```

| Field | Unit / accepted range |
| --- | --- |
| `schema` | Exact string `ping.telemetry.v1` |
| `battery_voltage` | V, 0–60 |
| `battery_percent` | %, 0–100 |
| `speed_mps` | m/s, −20–20; negative is reverse |
| `heading_deg` | Degrees clockwise from north, 0 inclusive to 360 exclusive |
| `pitch_deg` | Degrees, nose up positive, −90–90 |
| `roll_deg` | Degrees, right side down positive, −180–180 |
| `motor_temp_c` | °C, −40–150 |
| `signal_rssi_dbm` | dBm, −150–0 |
| `latency_ms` | ms, 0–60000; must be measured/reported by robot protocol |
| `distance_m` | m, 0–100000000 |
| `wheel_rpm` | Four numeric values, each −1000–1000, or unknown |
| `wheel_slip` | Four numeric values, each 0–1, or unknown |
| `motor_current_a` | Four numeric values, each 0–100 A, or unknown |

These are broad input validation limits for the test rover, not operational
safety limits. JSON strings, booleans, NaN/infinity, missing core channels,
invalid wheel counts, and out-of-range values reject the entire packet. Packets
over 4096 bytes are discarded up to the next newline. The next valid packet
recovers automatically. Serial reads are capped at 8192 bytes per application
update, with nonblocking `timeout=0`, and reconnect attempts occur every 2 s.
No data is written to the port. OS port-open duration remains driver-dependent.

`TelemetryManager` reports `connected` only after a validated packet. After 1 s
without one, status becomes `stale` and `state.sample` becomes `None`; an open
port alone is `waiting`. A disconnected transport immediately clears live
values. History (300 readings by default) remains explicitly historical.
Reconnect requires a new valid packet before showing current values.

For the real protocol, supply a `TelemetryDecoder` object to
`SerialTelemetrySource(port, decoder=...)`. Its `feed(data, now)` returns complete
immutable `TelemetrySample` tuples and `reset()` discards partial bytes on
disconnect. It also exposes `rejected_count`. To change adapters at runtime use
`manager.replace_source(new_source)`, which closes the old source and clears its
state/history. The simulator has a `paused` boolean to demonstrate freshness
loss and recovery without unplugging hardware.
