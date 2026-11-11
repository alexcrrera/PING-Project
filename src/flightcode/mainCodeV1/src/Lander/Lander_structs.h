#pragma once



#include <Arduino.h>
#include "../Utilities/Utilities.h"
#include "../Config/DataGroupsConfig.h"
#include "../StateMachine/StateMachine_utilities.h"


struct StateValidity
{
    bool positionValid = false;
    bool velocityValid = false;
    bool accelerationValid = false;
    bool attitudeValid = false;
    bool altitudeValid = false;
};

enum class AltitudeSource : uint8_t
{
    None,
    Lidar,
    VN300,
    Fused
};

enum class PositionSource : uint8_t
{
    None,
    VN300,
    Inertial,
    Fused
};

enum class VelocitySource : uint8_t
{
    None,
    VN300,
    Inertial,
    Fused,
    OpticalFlow
};

enum class AttitudeSource : uint8_t
{
    None,
    VN300,
    Fused
};

struct SolutionSource
{
    AltitudeSource altitude = AltitudeSource::None;
    PositionSource position = PositionSource::None;
    VelocitySource velocity = VelocitySource::None;
    AttitudeSource attitude = AttitudeSource::None;
};

enum LanderError : uint16_t
{
    LANDER_ERROR_NONE              = 0,

    LANDER_ERROR_NO_POSITION       = 1 << 0,
    LANDER_ERROR_NO_ALTITUDE       = 1 << 1,
    LANDER_ERROR_NO_ATTITUDE       = 1 << 2,
    LANDER_ERROR_NO_VELOCITY       = 1 << 3,

    LANDER_ERROR_VN300_UNAVAILABLE = 1 << 4,
    LANDER_ERROR_LIDAR_UNAVAILABLE = 1 << 5,
    LANDER_ERROR_GNSS_INVALID      = 1 << 6,

    LANDER_ERROR_SOLUTION_STALE    = 1 << 7
};

struct WheelData
{
    float RPM = 0.0f;
    float current_A = 0.0f;
    
    float estimated_torque_NM = 0.0f;
    float estimated_slip_ratio = 0.0f;
    
};

struct WGD
{
    static constexpr const GroupConfig& config = CommsConfig::WGD;

    WheelData front_left;
    WheelData front_right;
    WheelData rear_left;
    WheelData rear_right;
};


struct GPD{
    static constexpr const GroupConfig& config = CommsConfig::GPD;

    bool isValid = false;
    float latitude_deg = 0.0f;
    float longitude_deg = 0.0f;
    float altitude_MSL_m = 0.0f;
};

struct ATVL{
    static constexpr const GroupConfig& config = CommsConfig::ATVL;

    float BODY_velocity_X_SI = 0.0f;
    float BODY_velocity_Y_SI = 0.0f;
    float yaw_DEG = 0.0f;
    float pitch_DEG = 0.0f;
    float roll_DEG = 0.0f;
};

struct WSST{
    static constexpr const GroupConfig& config = CommsConfig::WSST;

    float RPM_FL = 0.0f;
    float RPM_FR = 0.0f;
    float RPM_RL = 0.0f;
    float RPM_RR = 0.0f;

    float estimated_slip_ratio_FL = 0.0f;
    float estimated_slip_ratio_FR = 0.0f;
    float estimated_slip_ratio_RL = 0.0f;
    float estimated_slip_ratio_RR = 0.0f;

};


struct ACCL{
    static constexpr const GroupConfig& config = CommsConfig::ACCL;

    float BODY_linear_acceleration_X_SI = 0.0f;
    float BODY_linear_acceleration_Y_SI = 0.0f;
    float BODY_linear_acceleration_Z_SI = 0.0f;
};

struct WCT{
    float estimated_torque_FL_NM = 0.0f;
    float estimated_torque_FR_NM = 0.0f;
    float estimated_torque_RL_NM = 0.0f;
    float estimated_torque_RR_NM = 0.0f;


};


struct GMBL{
    static constexpr const GroupConfig& config = CommsConfig::GMBL;

    float estimated_horizontal_distance_1_M = 0.0f;
    float estimated_horizontal_distance_2_M = 0.0f;
    uint8_t estimation_validity = 0;
    uint8_t gimbal_mode = 0;
    float lidar_distance_M = 0.0f;
    float pan_angle_DEG = 0.0f;
    float tilt_angle_DEG = 0.0f;
    
};




struct LanderState
{
    // Local NED position [m]
    NED_coordinates position;

    float altitude_M = 0.0f; // Altitude above ground level [m]

    // BODY velocity [m/s]
    BODY_coordinates velocity;




    // BODY linear acceleration [m/s^2]
    BODY_coordinates acceleration;

    // Attitude in Euler angles [deg]
    Rotation_Euler_coordinates attitude;

    // Body angular rates [deg/s]
    Rotation_Euler_coordinates angularVelocity;

    STATE_MACHINE_STATES state = STATE_MACHINE_STATES::AWAIT; // Current state of the lander

    StateValidity validity;
    
    WGD wheel_data;

    GPD group_GPS_data;
    GMBL group_GMBL_data;
    ATVL group_ATVL_data;
    WSST group_WSST_data;
    ACCL group_ACCL_data;
    WCT group_WCT_data;

    

};


struct LanderSolution
{
    LanderState state;
    
    SolutionSource source;

    uint16_t errors = LANDER_ERROR_NONE;
    uint32_t timestamp = 0;
};

