# PING rover firmware: Leonidas adaptation review

This is a design review of `mainCodeFlightV2`, not a hardware-ready rover build.
Keep the Leonidas flight project intact and make a separate rover firmware target.
The Teensy owns sensing, state estimation, drive control, safety, and telemetry.
The Raspberry Pi captures and streams video only. The ground station needs a
direct command/telemetry link to the Teensy, separate from the Pi video link.

Known hardware: Teensy 4.1, four 12 V Pololu 37D 70:1 gearmotors with 64 CPR
encoders, four Adafruit DRV8871 motor drivers, VectorNav IMU, the existing
optical-flow sensor, and Leonidas's Serial5 radio. Four ACS712 5 A current
sensors are under consideration. Confirm the current-sensor boards and wiring
before assigning pins or motor limits.

## What can be reused

| Leonidas code | Rover use |
| --- | --- |
| `FlightManager` update structure | Replace with `RoverManager` and a defined, timed sensor/command/estimator/output loop. |
| `TelemetryManager` serial framing and port handling | Rework into a versioned rover protocol with command sequence numbers, timestamps, validation, and acknowledgements. |
| `VN300`, `Lidar`, `OpticalFlow` drivers | Reuse only if the rover has those exact devices and electrical interfaces. Add measurement timestamps, timeouts, and rover coordinate transforms. |
| `PID` implementation | Reuse after checking timing, output limits, integrator reset, and saturation behavior with wheel speed control. 
| `StateMachine` concept | Replace flight states with , `DISARMED`, `READY`, `DRIVING`, and `FAULT`. |
| `FlightGuard` concept | Replace flight bounds with rover interlocks and make its result gate every motor output. |

The flight `ctrler`, `MotorManager`, `ActuatorPWM`, and aerodynamic
configuration are not rover implementations. They target one EDF ESC and four
vane servos, not four bidirectional wheel drives.

## Findings in the pasted code

1. `FlightGuard::isFlightConditionValid()` and
   `StateEstimator::isFlightConditionValid()` both return `true`. The checked
   flight bounds are reported but do not gate the motor outputs. The rover
   firmware must make safety checks authoritative before any wheel command.
2. `StateEstimator::estimatePosition_NED()` assigns zero to both horizontal
   coordinates each update. This estimator cannot be reused as rover odometry.
3. The optical-flow parser has packet checks, but flow validity does not expire
   when packets stop. Its `projectOpticalFlowToNED()` uses pitch and roll without
   yaw, so the claimed North/East result is not a complete world-frame rotation.
   Calibrate mounting direction, distance scaling, and body-frame velocity.
4. Incoming commands are handled by `TelemetryManager` after the motor update.
   The flight command parser has arm/disarm commands but no drive command,
   sequence number, command timeout, or emergency stop implementation.
5. The Leonidas telemetry is `$LNDAS` text at 115200 baud. The ground station's
   current serial adapter accepts receive-only JSON lines at 57600 baud and
   sends no drive commands. A new end-to-end protocol and host adapter are
   required before the GUI can drive real hardware.
6. There are no four-wheel encoder, per-wheel current, or bidirectional motor
   driver modules in this flight tree.

## Teensy data path

```
direct command link ----> validated command + heartbeat ----┐
4 encoders -----------┐                                       |
4 current sensors ----+--> timestamped samples --> estimator + drive ctroler
IMU ------------------+                          |            |
optical flow + range -┘                          |            v
                                          velocity / slip   4 wheel outputs
                                                |            ^
                                                └--> safety --┘
                                                      |
direct telemetry link <-------------------------------┘

Pi camera ------------------------------------> video stream to ground station
```

Use body-frame forward/lateral ground velocity and yaw rate as the core rover
state. Predict motion from calibrated IMU acceleration and yaw rate. Correct
ground velocity with valid optical flow and range. Treat encoder speed as a
wheel observation whose weight falls during slip; do not treat it as ground
speed during skidding. Use motor current and motor/wheel dynamics to estimate
torque and detect traction changes. Torque predicts acceleration, but cannot
recover an unknown constant ground velocity by itself. Integrate the estimated
velocity for local position, with uncertainty growing when flow is unavailable.



## Safety and integration gates

- Boot with all motor outputs disabled. Require an explicit arm command and
  healthy sensors/driver status.
- Apply a command heartbeat timeout on the Teensy; a stopped GUI or failed
  radio must command zero drive independently of the Pi.
- Include a physical emergency stop, output watchdog, overcurrent/undervoltage
  handling, and a fault state that needs deliberate reset.
- Keep the Pi out of the control loop. If a camera mount has physical pan/tilt
  motors, wire and command them through the Teensy. Digital zoom can remain in
  the ground station video view.
- Test the rover firmware without motors connected, then with lifted wheels,
  then on the ground at limited output.

## Hardware decisions needed before pin-level code

Confirm the per-wheel external current sensor boards, the motor and encoder
pin assignments, the physical emergency-stop wiring, and the radio packet
format used at the ground station. Keep Serial5 as the Teensy radio port. The
two available USB radios exchanged clean text at 57600 baud in both directions;
Leonidas currently configures Serial5 at 115200. Set both ends of the eventual
Teensy-to-radio UART connection to the same rate before field testing.

The Adafruit DRV8871 breakout exposes IN1/IN2 motor control and a resistor-set
current limit, but no per-wheel current measurement output. Its default limit
is about 2 A. Pololu's current 12 V 70:1 37D encoder variant lists a 5.5 A
stall current, so characterize the actual motor/driver combination under load
before selecting the current limit. The Pololu encoder variant has 64 counts
per motor-shaft revolution with full quadrature decoding, or 4480 per gearbox
output revolution at 70:1. Its encoder supply range starts above 3.3 V, and
its A/B outputs swing to that supply voltage. Teensy 4.1 GPIO is 3.3 V-only:
use suitable level shifting or a verified 3.3 V-compatible interface.

References: [Adafruit DRV8871 guide](https://learn.adafruit.com/adafruit-drv8871-brushed-dc-motor-driver-breakout),
[Pololu 70:1 encoder motor](https://www.pololu.com/product/4754), and
[Teensy 4.1 electrical pin limits](https://www.pjrc.com/store/teensy41.html).

If using ACS712 5 A sensors, power them and condition their outputs according
to the actual board. The ACS712 IC uses a 5 V supply, its zero-current output
is near 2.5 V, and its 5 A variant is nominally 185 mV/A. At +5 A the output
is about 3.425 V, above the Teensy 4.1 ADC's 3.3 V maximum. Add a suitable
voltage divider or ADC interface and calibrate each channel at zero current.
The nominal ±5 A measurement range also does not cover a 5.5 A motor stall
on the cited Pololu variant. See the [ACS712 datasheet](https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.ashx)
and [Teensy ADC limits](https://www.pjrc.com/store/teensy41.html).
