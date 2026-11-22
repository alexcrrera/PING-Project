#include "StateEstimator.h"
#include <math.h>


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


    const auto& vn = sensorMeasurements.vn300_data;
    const auto& gnss = vn.gnssSolution;
    auto& gpd = state.group_GPS_data;
    gpd.isValid = vn.gnssReceived && (millis() - vn.gnssReceivedAtMs < 2000) && gnss.GnssFix >= 3;
    gpd.numSats = gnss.NumSats;
    gpd.latitude_deg = gnss.Lat;
    gpd.longitude_deg = gnss.Lon;
    gpd.altitude_ellipsoid_m = gnss.Alt;
    gpd.velN = gnss.VelN; gpd.velE = gnss.VelE; gpd.velD = gnss.VelD;
    gpd.horizontalUncertainty_m = (gnss.PosUncertaintyN + gnss.PosUncertaintyE) * 0.5f;
    gpd.velocityUncertainty_mps = gnss.GnssVelUncertainty;

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


    // Both range estimators currently use the same LiDAR reading.
    const auto& lidar = sensorMeasurements.lidar_data;
    auto& gmbl = state.group_GMBL_data;
    const bool lidarValid = lidar.valid && millis() - lidar.receivedAtMs < 500;
    const float distance = lidarValid ? lidar.raw_distance_M : 0.0f;
    gmbl.lidar_distance_M = distance;
    gmbl.estimation_validity = 0;
    gmbl.target_validity = 0;
    gmbl.estimated_horizontal_distance_1_M = 0;
    gmbl.estimated_horizontal_distance_2_M = 0;
    if (flight_manager != nullptr)
    {
        const auto& gimbal = flight_manager->getGimbal();
        gmbl.gimbal_mode = static_cast<uint8_t>(gimbal.getMode());
        gmbl.pan_angle_DEG = gimbal.getPan_deg();
        gmbl.tilt_angle_DEG = gimbal.getTilt_deg();
        float north = 0, east = 0;
        const bool attitudeValid = vn.attitudeReceived && millis() - vn.attitudeReceivedAtMs < 2000;
        const auto& imu = vn.ybaLinearAccelGyro;
        if (lidarValid && attitudeValid && gimbal.projectRangeNed(distance, imu.Yaw, imu.Pitch, imu.Roll, north, east))
        {
            const float horizontal = hypotf(north, east);
            gmbl.estimated_horizontal_distance_1_M = horizontal;
            gmbl.estimated_horizontal_distance_2_M = horizontal;
            gmbl.estimation_validity = 3;
            const double cosLat = cos(gnss.Lat * 0.017453292519943295);
            if (gpd.isValid && fabs(cosLat) > 0.000001)
            {
                const double lat = gnss.Lat + north / 111319.49079327358;
                double lon = gnss.Lon + east / (111319.49079327358 * cosLat);
                if (lon > 180) lon -= 360;
                if (lon < -180) lon += 360;
                if (lat >= -90 && lat <= 90)
                {
                    gmbl.target1_lat = gmbl.target2_lat = lat;
                    gmbl.target1_lon = gmbl.target2_lon = lon;
                    gmbl.target_validity = 3;
                }
            }
        }
    }

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
    const auto& vn = sensorMeasurements.vn300_data;
    const auto& gnss = vn.gnssSolution;
    const auto& imu = vn.ybaLinearAccelGyro;
    // NED to VectorNav body (forward, right, down), then to PING body
    // (right, forward, up). Use true yaw, never the display yaw offset.
    if (!vn.gnssReceived || !vn.attitudeReceived || gnss.GnssFix < 3 ||
        millis() - vn.gnssReceivedAtMs >= 2000 || millis() - vn.attitudeReceivedAtMs >= 2000)
    {
        state.velocity = BODY_coordinates{};
        state.validity.velocityValid = false;
        return;
    }
    const float yaw = Utilities::degToRad(imu.Yaw);
    const float pitch = Utilities::degToRad(imu.Pitch);
    const float roll = Utilities::degToRad(imu.Roll);
    const float cy = cosf(yaw), sy = sinf(yaw);
    const float cp = cosf(pitch), sp = sinf(pitch);
    const float cr = cosf(roll), sr = sinf(roll);
    const float forward = cp*cy*gnss.VelN + cp*sy*gnss.VelE - sp*gnss.VelD;
    const float right = (sr*sp*cy-cr*sy)*gnss.VelN + (sr*sp*sy+cr*cy)*gnss.VelE + sr*cp*gnss.VelD;
    const float down = (cr*sp*cy+sr*sy)*gnss.VelN + (cr*sp*sy-sr*cy)*gnss.VelE + cr*cp*gnss.VelD;
    state.velocity.X_SI = right;
    state.velocity.Y_SI = forward;
    state.velocity.Z_SI = -down;
    state.validity.velocityValid = true;
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
