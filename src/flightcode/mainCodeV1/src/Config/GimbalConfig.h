#pragma once

#include "ActuatorsConfig.h"

namespace GimbalConfig
{
    // X1 and X2 are reserved for the gimbal when servos are enabled.
    constexpr bool servosEnabled = true;
    constexpr float updateFrequency = 50.0f;
    constexpr float panSpeed_deg_s = 45.0f;
    constexpr float tiltSpeed_deg_s = 45.0f;
    constexpr float panServoDirection = -1.0f;
    constexpr float tiltServoDirection = -1.0f;

    constexpr ActuatorPWM_config panServo = {
        .pin = ActuatorsConfig::Servo_X1_pin,
        .frequency = updateFrequency,
        .pulseMin = 1000,
        .pulseMax = 2000,
        .valueMin = 0.0f,
        .valueMax = 180.0f,
        .trim_deg = 90.0f,
        .resolution = 0.1f
    };

    constexpr ActuatorPWM_config tiltServo = {
        .pin = ActuatorsConfig::Servo_X2_pin,
        .frequency = updateFrequency,
        .pulseMin = 1000,
        .pulseMax = 2000,
        .valueMin = 0.0f,
        .valueMax = 180.0f,
        .trim_deg = 90.0f,
        .resolution = 0.1f
    };

    constexpr float panMin_deg = -90.0f;
    constexpr float panMax_deg = 90.0f;
    constexpr float tiltMin_deg = -90.0f;
    constexpr float tiltMax_deg = 90.0f;
}
