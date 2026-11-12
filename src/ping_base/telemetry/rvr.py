"""Decode rover groups and combine their latest readings by receive time."""

from math import hypot, isfinite, tau

from .model import RoverTelemetrySample, validate_sample


GROUP_EXPIRY = {
    "P2": 1.0, "P3": 1.5, "F": 2.5, "LP": 5.0, "P1": 1.5,
    "RGM": 6.0, "WGD": 5.0, "WSST": 1.0, "ACCL": 1.0, "GPD": 2.5, "GMBL": 5.0, "ATVL": 1.5,
}
BRAKE_FLAGS = {"[OK]": True, "[X]": False, "1": True, "0": False}


def _numbers(fields: tuple[str, ...], count: int) -> tuple[float, ...]:
    if len(fields) != count:
        raise ValueError(f"Expected {count} rover fields")
    values = tuple(map(float, fields))
    if not all(map(isfinite, values)):
        raise ValueError("Rover readings must be finite")
    return values


def _decode_fields(group: str, fields: tuple[str, ...]) -> dict:
    if group == "RGM":
        if len(fields) != 10 or not fields[0] or len(fields[0]) > 32:
            raise ValueError("Expected regime name and nine fields")
        dynamic, velocity, acceleration, yawRate, yawAcceleration, tilt, yaw, minOutput, maxOutput = _numbers(fields[1:], 9)
        if dynamic not in (0, 1) or min(velocity, acceleration, yawRate, yawAcceleration, tilt, yaw) < 0 or not 0 <= minOutput <= maxOutput <= 100:
            raise ValueError("Invalid regime limits")
        return {"regime_mode": fields[0], "regime_dynamic": bool(dynamic),
                "regime_max_velocity_mps": velocity, "regime_max_acceleration_mps2": acceleration,
                "regime_max_yaw_rate_dps": yawRate, "regime_max_yaw_acceleration_dps2": yawAcceleration,
                "regime_pitch_roll_limit_deg": tilt, "regime_yaw_limit_deg": yaw,
                "regime_min_output_percent": minOutput, "regime_max_output_percent": maxOutput}

    if group == "ATVL":
        vx, vy, yaw, pitch, roll = _numbers(fields, 5)
        return {"velocity_body_mps": (vx, vy), "speed_mps": hypot(vx, vy),
                "heading_deg": yaw % 360.0, "pitch_deg": pitch, "roll_deg": roll}

    if group == "WSST":
        values = _numbers(fields, 8)
        return {"wheel_rpm": values[:4], "wheel_slip": values[4:]}

    if group == "ACCL":
        return {"acceleration_mps2": _numbers(fields, 3)}

    if group == "GPD":
        valid, latitude, longitude, altitude = _numbers(fields, 4)
        if valid not in (0, 1) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Invalid GPD fix")
        return {"latitude_deg": latitude if valid else None,
                "longitude_deg": longitude if valid else None,
                "altitude_m": altitude if valid else None}

    if group == "GMBL":
        distance1, distance2, validity, mode, lidar, pan, tilt = _numbers(fields, 7)
        if validity not in range(4) or mode not in range(3):
            raise ValueError("Invalid gimbal validity mask or mode")
        mask = int(validity)
        if lidar < 0 or (mask & 1 and distance1 < 0) or (mask & 2 and distance2 < 0):
            raise ValueError("Valid gimbal distances must be nonnegative")
        return {"gimbal_pan_deg": pan, "gimbal_pitch_deg": tilt, "gimbal_mode": int(mode),
                "gimbal_lidar_distance_m": lidar if mask else None,
                "gimbal_distance_1_m": distance1 if mask & 1 else None,
                "gimbal_distance_2_m": distance2 if mask & 2 else None,
                "gimbal_validity": mask}

    if group == "WGD":
        values = _numbers(fields, 16)
        return {"wheel_rpm": values[0::4], "motor_current_a": values[1::4],
                "wheel_slip": values[3::4]}

    if group == "LP":
        return {"low_priority_fields": fields}

    if group == "F":
        if len(fields) == 3 and all(flag in BRAKE_FLAGS for flag in fields):
            return {}  # Current firmware bench packet.
        if len(fields) != 2 or fields[0] not in BRAKE_FLAGS:
            raise ValueError("Expected brake override and regime mode")
        return {"brake_override": BRAKE_FLAGS[fields[0]], "regime_mode": fields[1]}

    if len(fields) == 3:
        _numbers(fields, 3)
        return {}  # Bench readings have no assigned physical channels.

    if group == "P1":
        if len(fields) == 5:
            return _decode_fields("ATVL", fields)
        speed, yaw, pitch, roll = _numbers(fields, 4)
        return {"speed_mps": speed, "heading_deg": yaw % 360.0,
                "pitch_deg": pitch, "roll_deg": roll}

    if group == "P2":
        values = _numbers(fields, 13)
        return {"wheel_rpm": tuple(omega * 60 / tau for omega in values[:4]),
                "wheel_slip": values[4:8], "motor_current_a": values[8:12],
                "roll_deg": values[12]}

    values = _numbers(fields, 11)
    longitude, latitude, altitude, pitch, pan, distance1, distance2, validity = values[3:]
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError("Rover coordinates out of range")
    if validity not in range(4):
        raise ValueError("Invalid gimbal distance validity mask")
    mask = int(validity)
    if (mask & 1 and distance1 < 0) or (mask & 2 and distance2 < 0):
        raise ValueError("Valid gimbal distances must be nonnegative")
    return {"acceleration_mps2": values[:3], "longitude_deg": longitude,
            "latitude_deg": latitude, "altitude_m": altitude,
            "gimbal_pitch_deg": pitch, "gimbal_pan_deg": pan,
            "gimbal_distance_1_m": distance1 if mask & 1 else None,
            "gimbal_distance_2_m": distance2 if mask & 2 else None,
            "gimbal_validity": mask}


class RoverGroups:
    def __init__(self):
        self._latest: dict[str, tuple[float, tuple[str, ...], dict]] = {}

    @property
    def latest_frames(self) -> dict[str, tuple[float, tuple[str, ...]]]:
        return {tag: (timestamp, fields) for tag, (timestamp, fields, _) in self._latest.items()}

    def reset(self) -> None:
        self._latest.clear()

    def decode(self, line: bytes, now: float) -> RoverTelemetrySample:
        frame = line.rstrip(b"\r").decode("ascii")
        if not frame.endswith("*") or "*" in frame[:-1] or "$" in frame[1:]:
            raise ValueError("Invalid rover frame delimiters")
        _, group, *tokens = frame[:-1].split(",")
        fields = tuple(token.strip() for token in tokens)
        if group not in GROUP_EXPIRY or not fields or not all(fields):
            raise ValueError("Unknown or empty rover group")
        values = _decode_fields(group, fields)
        validate_sample(RoverTelemetrySample(received_at=now, **values))
        self._latest[group] = (now, fields, values)

        merged = {}
        # Named groups take precedence over legacy readings for the same channels.
        for tag in GROUP_EXPIRY:
            timestamp, _, channels = self._latest.get(tag, (now, (), {}))
            if now - timestamp < GROUP_EXPIRY[tag]:
                merged.update(channels)
        return RoverTelemetrySample(received_at=now, **merged)
