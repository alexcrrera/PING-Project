
#pragma once
#ifndef SAFETY_BOUNDS_H
#define SAFETY_BOUNDS_H
#include "../Utilities/Utilities.h"

/*
SAFETY PARAMETERS THAT CAN TOGGLE ABORT CONDITIONS

*/

namespace SafetyBounds {

    constexpr float max_horizontal_velocity_ms = 2.0f;



    constexpr float max_horizontal_acceleration_ms2 = 7.0f;


    constexpr float max_yaw_velocity_degs = 40.0f;

    constexpr float max_yaw_acceleration_degs2 = 2500.0f;

    constexpr float yaw_abort_angle_deg = 99999.0f; // yaw angle that will trigger an abort
    constexpr float pitch_roll_abort_angle_deg = 45.0f;

}

#endif