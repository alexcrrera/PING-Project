#pragma once
#ifndef UTILITIES_H
#define UTILITIES_H



#include "Arduino.h"




struct PID_Gains{
    float kp = 0.0f;
    float ki = 0.0f;
    float kd = 0.0f;
};

struct Vector3
{
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};

struct NED_coordinates {
    // Position -> units are meters
    // velocity -> units are m/s ...
    float North_SI = 0.0f;
    float East_SI = 0.0f;
    float Down_SI = 0.0f;
};

struct BODY_coordinates {
    // Position -> units are meters
    // velocity -> units are m/s ...
    float X_SI = 0.0f;
    float Y_SI = 0.0f;
    float Z_SI = 0.0f;
};







struct Rotation_Euler_coordinates {
    float Roll_SI = 0.0f;
    float Pitch_SI = 0.0f;
    float Yaw_SI = 0.0f;
};

template<typename T>
struct ParameterConfig
{
    T min; 
    T max;
    T default_;
};

enum class OutputType{
    SUCCESS,
    CMD,
    PROTECTED,
    PARAMETER,
    STATE,
    SAFETY,
    SENSOR,
    ACTUATOR,
    COMMS,
    TIMEOUT,
    MISC
};







namespace Utilities{

    constexpr float GRAVITY_MS2 = 9.80665;  
    
    float clamping(float u, float u_max);
    
    float EWA(float alpha, float u, float measurement);

    float degToRad(float deg);
 
   
   
    //bool isBounded(float u, float u_min, float u_max);
    constexpr bool isBounded(float value,float minValue,float maxValue){return value >= minValue &&value <= maxValue;}
    bool isSimpleBouded(float u, float u_max);

    float distance1D(float u, float u_ref);
    float distance2D(float x, float y, float x_ref, float y_ref);
    float distance3D(float x, float y, float z, float x_ref, float y_ref, float z_ref);
    float distance3D(const Vector3& p, const Vector3& p_ref);



}
#endif
