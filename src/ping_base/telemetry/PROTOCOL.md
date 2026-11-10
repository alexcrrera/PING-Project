# Prototype telemetry protocol

The rover's actual firmware protocol has not been supplied. This receive-only
adapter demonstrates USB telemetry at **57600 baud**, 8 data bits, no parity,
1 stop bit. It does not implement rover control, traction optimization, or
transmit commands. Verify the firmware format before using real readings.

The dashboard's connection dialog starts at 57600 baud, which was verified
between the connected COM3 and COM4 radios. The Leonidas firmware currently
configures Serial5 at 115200 baud, so that setting must be reconciled before
connecting its Teensy to these radios. Under **Radio Link**, the GUI shows whether the
selected host port opened, how many raw bytes arrived, and the last complete
line even when this provisional JSON decoder rejects it. A `$LNDAS` line
therefore confirms reception but will not populate rover metrics until a
matching protocol adapter is implemented. The baud rate is editable; use
the sender's actual rate for the prototype JSON stream described below.

The explicit **Radio bench** source also sends `TEST:HELLO,<sequence>\n` on a
button press and `DRIVE:<sequence>,<throttle>,<steering>,<brake>\n` about every
100 ms while open. Throttle and steering are in [-1, 1]; brake is 0 or 1.
It also runs the virtual terrain and sends its simulated readings as
`$PING,1,STATE,<monotonic_ms>,<ground_speed_mps>,<heading_deg>,<pitch_deg>,<roll_deg>,<battery_v>,<battery_percent>,<distance_m>,*\n`
and `$PING,1,WHEELS,<monotonic_ms>,<four_rpm>,<four_current_a>,<four_slip>,*\n`
at approximately 10 Hz. Wheel order is FL, FR, RL, RR in each group. This is
a link and virtual-operation test, not the final rover protocol. It sends no
ARM command. Incoming arbitrary lines appear as raw text; they do not replace
the virtual terrain readings. Use one USB radio in the GUI and a serial app on
the other, both at 57600 baud for the verified COM3/COM4 pair. The virtual
terrain remains usable if the radio is unplugged.

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
