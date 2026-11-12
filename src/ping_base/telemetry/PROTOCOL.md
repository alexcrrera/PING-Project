# Serial telemetry protocol

Use **USB / serial telemetry and gimbal** in the dashboard with the receiving radio at
**57600 baud**, 8 data bits, no parity, and 1 stop bit. **Radio Link** shows the
port status, byte count, and last received line. Gimbal controls send explicit
newline-terminated `GIMBAL_MODE:<0|1|2>`, `GIMBAL_AIM:<pan>,<tilt>`, and
`GIMBAL_HOME:` commands. Angles are degrees relative to the rover body.

## Drive commands

The serial source sends `DRIVE:<throttle>,<steering>,<brake>\n`,
`STICK:<pan>,<tilt>\n`, `LEFT:<x>,<y>\n` and `TRIG:<l2>,<r2>\n` at approximately 25 Hz.
LEFT uses positive Y down. Trigger values are 0 to 1. Axes are normalized to
[-1, 1], with positive steering and pan to the right and positive tilt up.
The brake value is 0 or 1. Keyboard W/S and A/D control throttle and steering.
The PS4 uses R2 for throttle, L2 for brake, left-stick X for steering, and
right-stick X/Y for pan/tilt input.

PS4 button down events are sent once as `BUTTON:<name>\n`. The keyboard B
key and PS4 Options button send `BUTTON:BRAKE\n` on each press. The
CommandHandler exposes the latest button and an event sequence counter.

`getDriveInput()` exposes the latest command to firmware. After 500 ms without
a DRIVE frame, it returns zero axes and brake enabled. The drive motor
controller must consume this state.

## Rover groups

Each frame is `$RVR,<group>,<comma-separated fields>*\n`. CRLF is also accepted.
Groups arrive independently and update the latest available readings.

When sending wheel data:
Front-Left
Front-right
Rear-left
Rear-right

| Group | Rate | Fields in wire order |
| --- | --- | --- |
| `ATVL` | 15 Hz | Body velocity X and Y (m/s), yaw, pitch, roll (degrees) |
| `WSST` | 5 Hz | Four wheel angular speeds (RPM), four slip ratios (0–1)|
| `ACCL` | 5 Hz | Acceleration X/Y/Z (m/s²), linearised (no gravity) in the body frame |
| `GPD` | 2 Hz | Availability (0 no, 1 yes), latitude longitude, altitude |
| `GMBL` | 0.5 Hz | estimated distance horizontal 1, estimated distance 2, estimation validity (0 none, 1 estim good 2 bad, 2: 1 bad 2 good, 3: both good (we use different methods to calculate the horizontal distance from the rover and the measured point with the lidar )), gimbal mode (0: free, 1: yaw follow, 2: yaw and pitch follow), lidar distance, camera pan (body), pitch (body) caemra |
| `WGD` | 0.5 Hz (disabled) | RPM, current (A), torque (Nm), slip ratio for each wheel in FL, FR, RL, RR order |

Firmware rates and per-port enable flags are in `DataGroupsConfig.h`.
`WCT` and `BRK` are reserved for separate wheel-current/torque and brake packets.




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
OS port-open duration remains driver-dependent.

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

## RGM regime group

The Teensy sends `$RVR,RGM,<state>,<dynamic>,<max_velocity>,<max_acceleration>,<max_yaw_rate>,<max_yaw_acceleration>,<pitch_roll_limit>,<yaw_limit>,<min_output>,<max_output>*\n` every 2 seconds. State is text; dynamic is 0 or 1. Units are m/s, m/s², degrees/s, degrees/s², degrees, degrees, percent and percent, respectively. The limits are obtained from the state machine's current regime. RGM is enabled for radio and USB. In USB base-station format it is emitted as a separate group frame. The GUI expires regime fields after 6 seconds without a new RGM frame while other frames continue.

The target-speed gauge shows the local drive request. Its m/s readout is an estimate computed as throttle multiplied by the latest maximum velocity, with zero when braking; it is not a rover-reported target.
