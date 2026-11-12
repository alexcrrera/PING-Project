# PING Controller Serial Interface

## Scope and status

The controller team needs only the six quantities below. This is the intended data contract for information delivered to the controller team. The exact data flow and mapping between these quantities and Serial4 messages have not yet been agreed.

**The six-item contract is not yet implemented in the firmware.** The current firmware sends the ATVL group when controller group output is enabled. ATVL contains body velocity X and Y, measured yaw, pitch and roll; it does not contain the six requested control quantities. Do not interpret ATVL values as the requested targets or limits.

## Required information

| Quantity | Meaning | Data type and units | Status |
|---|---|---|---|
| Target velocity | Requested rover velocity | Numeric; units, axis and sign convention to be agreed | To be specified |
| Target yaw or target yaw rate | Requested heading or turning rate | Numeric; angle versus rate and corresponding units to be decided | Undecided |
| Maximum velocity | Velocity limit | Numeric; units and sign convention to be agreed | To be specified |
| Maximum yaw rate | Turning-rate limit | Numeric; units and sign convention to be agreed | To be specified |
| Maximum motor output or thrust | Upper output limit | Numeric percentage from 0 to 100.0 | Range specified |
| Traction control enabled | Whether traction control is enabled | Boolean; wire representation to be agreed | To be specified |

The interface will not include gimbal data for the controller team. Message names, field order, update frequency, numeric precision, validity handling and timeout behavior remain to be defined. No example packet is specified until those decisions are made.

## Existing serial transport

The current Teensy configuration assigns the controller link to Serial4 at 115200 baud, using UART 8N1. Serial3 is assigned to optical flow. Connect each device's TX to the other device's RX and connect a common ground; verify electrical voltage compatibility. The Serial4 implementation has not been verified on hardware.

The existing telemetry format is ASCII `$RVR,<GROUP>,<fields>*` followed by LF. Incoming commands use `IDENTIFIER:payload` followed by LF or CR. This existing framing does not establish a schema for the six requested quantities, and it does not provide an automatic Serial4 command acknowledgement.

## Controller to Teensy outputs shown in the diagram

The diagram shows three values for each of wheels 1, 2, 3 and 4 returning from the controller to the Teensy:

| Diagram notation | Tentative interpretation | Cardinality |
|---|---|---:|
| ω₁,₂,₃,₄ | Wheel angular velocities | 4 |
| τ̃₁,₂,₃,₄ | Estimated wheel torques | 4 |
| i₁,₂,₃,₄ | Wheel or motor currents | 4 |

These labels are a reading of the handwriting, not a confirmed interface definition. The intended distinction between measurements, estimates and commands, units, sign conventions, wheel numbering and output behavior must be agreed. The diagram does not establish a Serial4 message format or prove that these outputs are currently implemented. The controller-bound side of the diagram shows target velocity, target yaw, constraints and mode, corresponding to the required information above; yaw versus yaw rate is still undecided.
