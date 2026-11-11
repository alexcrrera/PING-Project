#pragma once
#ifndef FLIGHT_REGIME_CONFIG_H
#define FLIGHT_REGIME_CONFIG_H

#include "../Utilities/Utilities.h"
#include "Arduino.h"

#include "../Config/SafetyBounds.h"



struct FlightRegimeData
{
    char name[20];
    bool isDynamic = true; // if true, the rover is in flight and can move, if false, the lander is on the ground and should not move


   
    float max_horizontal_acceleration_ms2 = 0.0f;
    float max_horizontal_velocity_ms = 0.0f;

    float max_yaw_velocity_degs = 0.0f;
    float max_yaw_acceleration_degs2 = 0.0f;
   

    float pitch_roll_abort_angle_deg = 0.0f;
    float yaw_abort_angle_deg = 0.0f;

    float min_thrust_percentage = 0.0f;
    float max_thrust_percentage = 0.0f;



};


namespace FlightRegimeConfig {

    // Values for configuring take off, navigation and landing.
    // These are not safety limiters - see SafetyBounds.h


 

     inline FlightRegimeData NAVIGATION_TRACTION{
        .name = "TRACTION",
        .isDynamic = true,

        .max_horizontal_acceleration_ms2 = 2.0f,
        .max_horizontal_velocity_ms = 0.5f,


        .max_yaw_velocity_degs = 30.0f,

        .max_yaw_acceleration_degs2 = 2500.0f,

        .pitch_roll_abort_angle_deg = 15.0f,
        .yaw_abort_angle_deg = 9999.0f,

        .min_thrust_percentage = 0.0f,
        .max_thrust_percentage = 100.0f,



    };




     inline FlightRegimeData FULLBRAKE{
        .name = "FULL BRAKE",
        .isDynamic = false,

        .max_horizontal_acceleration_ms2 = 0.0f,
        .max_horizontal_velocity_ms = 0.0f,


        .max_yaw_velocity_degs = 0.0f,

        .max_yaw_acceleration_degs2 = 0.0f,

        .pitch_roll_abort_angle_deg = 15.0f,
        .yaw_abort_angle_deg = 9999.0f,

        .min_thrust_percentage = 0.0f,
        .max_thrust_percentage = 0.0f,



    };

    inline auto NAVIGATION_NO_TRACTION = NAVIGATION_TRACTION; // same as traction, placeholder so far
    inline auto NAVIGATION_OBSTACLE = NAVIGATION_TRACTION; // same as traction, but the rover is in obstacle mode - reduced velocity, placeholder so far


}

#endif