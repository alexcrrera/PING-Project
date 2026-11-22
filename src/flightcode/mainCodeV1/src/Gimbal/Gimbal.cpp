#include "Gimbal.h"

#include <math.h>
#include "../Config/GimbalConfig.h"
#include "../FlightManager/FlightManager.h"

namespace
{
    float wrapAngle(float angle)
    {
        angle = fmodf(angle + 180.0f, 360.0f);
        if (angle < 0.0f)
            angle += 360.0f;
        return angle - 180.0f;
    }
}

void Gimbal::begin(FlightManager* manager)
{
    flightManager = manager;
    lastUpdateTime = millis();
    if (GimbalConfig::servosEnabled)
    {
        panServo.attach(GimbalConfig::panServo);
        tiltServo.attach(GimbalConfig::tiltServo);
    }
    servoHandler.begin(GimbalConfig::updateFrequency, this, &Gimbal::actuate);
}

void Gimbal::update()
{
    if (flightManager == nullptr)
        return;
    const uint32_t now = millis();
    const float dt = constrain((now - lastUpdateTime) * 0.001f, 0.0f, 0.1f);
    lastUpdateTime = now;
    updateAngles();

    const auto input = flightManager->getCommandHandler().getDriveInput();
    const auto& attitude = flightManager->getLander().getState().attitude;
    if (isfinite(attitude.Yaw_SI) && isfinite(attitude.Pitch_SI))
    {
        if (input.cameraPan != 0.0f)
        {
            pan_deg = constrain(pan_deg + input.cameraPan * GimbalConfig::panSpeed_deg_s * dt,
                                GimbalConfig::panMin_deg, GimbalConfig::panMax_deg);
            targetYaw_deg = attitude.Yaw_SI + pan_deg;
        }
        if (input.cameraTilt != 0.0f)
        {
            tilt_deg = constrain(tilt_deg + input.cameraTilt * GimbalConfig::tiltSpeed_deg_s * dt,
                                 GimbalConfig::tiltMin_deg, GimbalConfig::tiltMax_deg);
            targetPitch_deg = attitude.Pitch_SI + tilt_deg;
        }
    }
    servoHandler.handle();
}

bool Gimbal::setMode(GimbalMode newMode)
{
    if (newMode != GimbalMode::FREE && newMode != GimbalMode::YAW_FOLLOW &&
        newMode != GimbalMode::YAW_PITCH_FOLLOW)
        return false;
    if (flightManager == nullptr)
        return false;
    updateAngles();
    const auto& attitude = flightManager->getLander().getState().attitude;
    if (!isfinite(attitude.Yaw_SI) || !isfinite(attitude.Pitch_SI))
        return false;
    targetYaw_deg = attitude.Yaw_SI + pan_deg;
    targetPitch_deg = attitude.Pitch_SI + tilt_deg;
    mode = newMode;
    return true;
}

bool Gimbal::setAngles(float pan, float tilt)
{
    if (flightManager == nullptr || !isfinite(pan) || !isfinite(tilt))
        return false;
    const auto& attitude = flightManager->getLander().getState().attitude;
    if (!isfinite(attitude.Yaw_SI) || !isfinite(attitude.Pitch_SI))
        return false;
    pan_deg = constrain(pan, GimbalConfig::panMin_deg, GimbalConfig::panMax_deg);
    tilt_deg = constrain(tilt, GimbalConfig::tiltMin_deg, GimbalConfig::tiltMax_deg);
    targetYaw_deg = attitude.Yaw_SI + pan_deg;
    targetPitch_deg = attitude.Pitch_SI + tilt_deg;
    return true;
}

bool Gimbal::home()
{
    if (flightManager == nullptr)
        return false;

    const auto& attitude = flightManager->getLander().getState().attitude;
    if (!isfinite(attitude.Yaw_SI) || !isfinite(attitude.Pitch_SI))
        return false;

    // Face along the rover's yaw and level the camera in the world frame.
    return setAngles(0.0f, -attitude.Pitch_SI);
}

void Gimbal::updateAngles()
{
    const auto& attitude = flightManager->getLander().getState().attitude;
    if (!isfinite(attitude.Yaw_SI) || !isfinite(attitude.Pitch_SI))
        return;

    if (mode == GimbalMode::FREE)
        pan_deg = constrain(wrapAngle(targetYaw_deg - attitude.Yaw_SI),
                            GimbalConfig::panMin_deg, GimbalConfig::panMax_deg);
    if (mode != GimbalMode::YAW_PITCH_FOLLOW)
        tilt_deg = constrain(targetPitch_deg - attitude.Pitch_SI,
                             GimbalConfig::tiltMin_deg, GimbalConfig::tiltMax_deg);
}

void Gimbal::actuate()
{
    if (GimbalConfig::servosEnabled)
    {
        panServo.write(GimbalConfig::panServoDirection * pan_deg);
        tiltServo.write(GimbalConfig::tiltServoDirection * tilt_deg);
    }
}

// Gimbal pan is right-positive and tilt is up-positive. VN attitude uses
// forward/right/down body axes and yaw clockwise from north.
bool Gimbal::projectRangeNed(float range_m, float yaw_deg, float pitch_deg, float roll_deg,
                             float& north_m, float& east_m) const
{
    if (!isfinite(range_m) || range_m <= 0 || !isfinite(yaw_deg) ||
        !isfinite(pitch_deg) || !isfinite(roll_deg)) return false;
    const float k = 0.017453292519943295f;
    const float yaw = yaw_deg*k, pitch = pitch_deg*k, roll = roll_deg*k;
    const float pan = pan_deg*k, tilt = tilt_deg*k;
    const float x = cosf(tilt)*cosf(pan), y = cosf(tilt)*sinf(pan), z = -sinf(tilt);
    const float cy=cosf(yaw), sy=sinf(yaw), cp=cosf(pitch), sp=sinf(pitch), cr=cosf(roll), sr=sinf(roll);
    north_m = range_m*(cp*cy*x + (sr*sp*cy-cr*sy)*y + (cr*sp*cy+sr*sy)*z);
    east_m = range_m*(cp*sy*x + (sr*sp*sy+cr*cy)*y + (cr*sp*sy-sr*cy)*z);
    return isfinite(north_m) && isfinite(east_m);
}
