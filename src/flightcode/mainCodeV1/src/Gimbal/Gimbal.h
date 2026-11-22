#pragma once

#include <Arduino.h>
#include <Handler.h>
#include "../ActuatorPWM/ActuatorPWM.h"

class FlightManager;

enum class GimbalMode : uint8_t
{
    FREE = 0,
    YAW_FOLLOW = 1,
    YAW_PITCH_FOLLOW = 2
};

class Gimbal
{
public:
    void begin(FlightManager* flightManager);
    void update();

    bool setMode(GimbalMode mode);
    bool setAngles(float pan_deg, float tilt_deg);
    bool home();
    // Project a line-of-sight range to north/east using FRD sensor attitude.
    bool projectRangeNed(float range_m, float yaw_deg, float pitch_deg, float roll_deg,
                         float& north_m, float& east_m) const;

    GimbalMode getMode() const { return mode; }
    float getPan_deg() const { return pan_deg; }
    float getTilt_deg() const { return tilt_deg; }

private:
    void actuate();
    void updateAngles();

    FlightManager* flightManager = nullptr;
    ActuatorPWM panServo;
    ActuatorPWM tiltServo;
    Handler servoHandler;
    GimbalMode mode = GimbalMode::YAW_PITCH_FOLLOW;
    float pan_deg = 0.0f;
    float tilt_deg = 0.0f;
    float targetYaw_deg = 0.0f;
    float targetPitch_deg = 0.0f;
    uint32_t lastUpdateTime = 0;
};
