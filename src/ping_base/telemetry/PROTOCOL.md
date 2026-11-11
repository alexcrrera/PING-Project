# Serial telemetry protocol

Use **USB / serial receive only** in the dashboard with the receiving radio at
**57600 baud**, 8 data bits, no parity, and 1 stop bit. **Radio Link** shows the
port status, byte count, and last received line. This source sends no commands.

## Rover groups

Each frame is `$RVR,<group>,<comma-separated fields>*\n`. CRLF is also accepted.
Groups arrive independently and update the latest available readings.

| Group | Rate | Fields in wire order |
| --- | --- | --- |
| `P1` | 10 Hz | Body velocity X and Y (m/s), yaw, pitch, roll (degrees) |
| `P2` | 5 Hz | Four wheel angular speeds (rad/s), four slip ratios (0–1), four currents (A), roll (degrees) |
| `P3` | 2 Hz | Acceleration X/Y/Z (m/s²), longitude and latitude (degrees), altitude (m), gimbal pitch and pan (degrees), distance estimates 1 and 2 (m), validity mask |
| `F` | 1 Hz | Brake override (`[OK]`/`1` for true, `[X]`/`0` for false), regime mode |
| `LP` | 0.5 Hz | Raw fields shown under Radio Link until their meanings are defined |

For `P1`, the dashboard displays both velocity components and their magnitude
as ground speed. Example `$RVR,P1,0.00,123.23,270.00,2.00,-3.00*` uses the
firmware's current test velocity. The older four-field layout (ground speed,
yaw, pitch, roll) still decodes.

The order within each four-wheel block is front-left, front-right, rear-left,
rear-right. The dashboard converts angular speed to RPM, normalizes yaw to
0–360°, and uses `P2` roll when `P1` roll is unavailable. In the validity mask,
bit 0 is distance 1 and bit 1 is distance 2. A clear bit leaves that range blank.

The current three-number `P1`, `P2`, `P3` frames and three-flag `F` frames are
accepted as bench traffic. These placeholder fields have no assigned readings.
Missing channels stay blank. The cached `P1`, `P2`, `P3`, `F`, and `LP` readings
expire after 1.5, 1, 1.5, 2.5, and 5 seconds respectively as the stream updates.
Reconnecting discards cached group readings and partial frames.

## Radio bench and legacy JSON

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

The legacy wire format is one UTF-8 JSON object per newline (`\n`, optionally
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
