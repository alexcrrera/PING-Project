#include "StateEstimator.h"


#include "StateEstimator.h"
#include "../Lander/Lander.h"
#include"../FlightManager/FlightManager.h"



void StateEstimator::begin(FlightManager* flightManager_)
{
    flight_manager = flightManager_; // pass flight manager object to state estimator
    //Serial.println("STATE ESTIMATOR: BEGIN");
    
}



bool StateEstimator::isFlightConditionValid(){
    return true; // placeholder for actual flight condition validation logic
}

void StateEstimator::update(SensorMeasurements& sensorMeasurements)
{
    estimateAttitude_EULER(state, sensorMeasurements);
    
    estimateVelocity_EULER(state, sensorMeasurements);

    estimateAcceleration_BODY(state, sensorMeasurements);
    estimateVelocity_BODY(state, sensorMeasurements);
    estimatePosition_NED(state, sensorMeasurements);

    updateStructs(state, sensorMeasurements);
}


void StateEstimator::updateStructs(LanderState& state, const SensorMeasurements& sensorMeasurements)
{


    // ACCL
    state.group_ACCL_data.BODY_linear_acceleration_X_SI = state.acceleration.X_SI;
    state.group_ACCL_data.BODY_linear_acceleration_Y_SI = state.acceleration.Y_SI;
    state.group_ACCL_data.BODY_linear_acceleration_Z_SI = state.acceleration.Z_SI;


    // Update ATVL
    state.group_ATVL_data.BODY_velocity_X_SI = state.velocity.X_SI;
    state.group_ATVL_data.BODY_velocity_Y_SI = state.velocity.Y_SI;
    state.group_ATVL_data.yaw_DEG = state.attitude.Yaw_SI;
    state.group_ATVL_data.pitch_DEG = state.attitude.Pitch_SI;
    state.group_ATVL_data.roll_DEG = state.attitude.Roll_SI;    

    // WSST uses the same wheel data as the previous wheel telemetry.
    const auto& wheels = state.wheel_data;
    auto& wsst = state.group_WSST_data;
    wsst.RPM_FL = wheels.front_left.RPM;
    wsst.RPM_FR = wheels.front_right.RPM;
    wsst.RPM_RL = wheels.rear_left.RPM;
    wsst.RPM_RR = wheels.rear_right.RPM;
    wsst.estimated_slip_ratio_FL = wheels.front_left.estimated_slip_ratio;
    wsst.estimated_slip_ratio_FR = wheels.front_right.estimated_slip_ratio;
    wsst.estimated_slip_ratio_RL = wheels.rear_left.estimated_slip_ratio;
    wsst.estimated_slip_ratio_RR = wheels.rear_right.estimated_slip_ratio;
}



void StateEstimator::estimateAcceleration_BODY(LanderState& state, const SensorMeasurements& sensorMeasurements)
{

    state.acceleration.X_SI = sensorMeasurements.vn300_data.ybaLinearAccelGyro.LinAccelX; // Forward acceleration
    state.acceleration.Y_SI = sensorMeasurements.vn300_data.ybaLinearAccelGyro.LinAccelY; // Right acceleration
    state.acceleration.Z_SI = sensorMeasurements.vn300_data.ybaLinearAccelGyro.LinAccelZ; // Up acceleration

    state.validity.accelerationValid = true; // Assuming acceleration is valid if VN300 data is available

}




void StateEstimator::estimateVelocity_BODY(LanderState& state, const SensorMeasurements& sensorMeasurements)
{
   
    state.velocity.X_SI = 0.5f; // Placeholder for actual velocity estimation logic
    state.velocity.Y_SI = 0.1f; // Placeholder for actual velocity estimation logic
    state.velocity.Z_SI = 12.58;
    state.validity.velocityValid = true; // Assuming velocity is valid if VN300 data is available
}



void StateEstimator::estimatePosition_NED(LanderState& state, const SensorMeasurements& sensorMeasurements)
{
    // Convert latitude, longitude, and altitude to NED coordinates

    state.position.North_SI = 0.0;
    state.position.East_SI = 0.0;
    state.position.Down_SI = -sensorMeasurements.lidar_data.altitude_M; // Use Lidar altitude for Down coordinate
    state.altitude_M = sensorMeasurements.lidar_data.altitude_M; // Store altitude in the state
    state.validity.positionValid = true; // Assuming position is valid if Lidar data is available
    state.validity.altitudeValid = true; // Assuming altitude is valid if Lidar data is available
}


void StateEstimator::estimateVelocity_EULER(LanderState& state, const SensorMeasurements& sensorMeasurements)
{
    // use gyroscope data to estimate angular velocity in Euler angles
    float GyroX = sensorMeasurements.vn300_data.ybaLinearAccelGyro.GyroX;
    float GyroY = sensorMeasurements.vn300_data.ybaLinearAccelGyro.GyroY;
    float GyroZ = sensorMeasurements.vn300_data.ybaLinearAccelGyro.GyroZ;   
    state.angularVelocity.Roll_SI = GyroX;
    state.angularVelocity.Pitch_SI = GyroY;
    state.angularVelocity.Yaw_SI = GyroZ;
   
}


void StateEstimator::estimateAttitude_EULER(LanderState& state, const SensorMeasurements& sensorMeasurements)
{
    // use VN300 data to estimate attitude in Euler angles
    float Yaw = sensorMeasurements.vn300_data.ybaLinearAccelGyro.Yaw + yawZeroOffset; // apply yaw zero offset
    float Pitch = sensorMeasurements.vn300_data.ybaLinearAccelGyro.Pitch;
    float Roll = sensorMeasurements.vn300_data.ybaLinearAccelGyro.Roll;
    state.attitude.Roll_SI = Roll;
    state.attitude.Pitch_SI = Pitch;
    state.attitude.Yaw_SI = Yaw;
}