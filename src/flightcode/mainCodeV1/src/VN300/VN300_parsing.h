#pragma once


#ifndef VN300_PARSING_H
#define VN300_PARSING_H


#include <Arduino.h>
#include <textparser.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

#include "VN300_data_structs.h"



namespace VN300Parsing
{
    inline TextParser commaParser(",");
    bool parse_GNSS_Solution_LLA(char *payload, VN300Measurement& measurement);
    void parse_INS_Solution_LLA(char *payload, VN300Measurement& measurement);
    void parse_YPR_LinearAccel_Gyro(char *payload, VN300Measurement& measurement);
    void parse_YBA_LinearAccel_Gyro(char *payload, VN300Measurement& measurement);
}
void VN300Parsing::parse_YBA_LinearAccel_Gyro(char *payload, VN300Measurement& measurement){
    
    char header[7];

    commaParser.parseLine(payload,header,

        measurement.ybaLinearAccelGyro.Yaw,
        measurement.ybaLinearAccelGyro.Pitch,
        measurement.ybaLinearAccelGyro.Roll,
        measurement.ybaLinearAccelGyro.LinAccelX,
        measurement.ybaLinearAccelGyro.LinAccelY,
        measurement.ybaLinearAccelGyro.LinAccelZ,

        measurement.ybaLinearAccelGyro.GyroX,
        measurement.ybaLinearAccelGyro.GyroY,
        measurement.ybaLinearAccelGyro.GyroZ
    );
}

bool VN300Parsing::parse_GNSS_Solution_LLA(char* payload, VN300Measurement& measurement)
{
    // Register 58 ASCII has no binary padding field. Parse into a temporary
    // solution so a truncated or malformed response cannot corrupt the last fix.
    const char* prefix = "$VNRRG,58,";
    if (strncmp(payload, prefix, strlen(prefix)) != 0) return false;
    const char* checksum = strchr(payload, '*');
    if (!checksum || strlen(checksum + 1) != 2) return false;
    unsigned int expected = 0;
    for (const char* digit = checksum + 1; *digit; ++digit)
    {
        expected <<= 4;
        if (*digit >= '0' && *digit <= '9') expected += *digit - '0';
        else if (*digit >= 'A' && *digit <= 'F') expected += *digit - 'A' + 10;
        else if (*digit >= 'a' && *digit <= 'f') expected += *digit - 'a' + 10;
        else return false;
    }
    unsigned int actual = 0;
    for (const char* byte = payload + 1; byte < checksum; ++byte) actual ^= static_cast<uint8_t>(*byte);
    if (actual != expected) return false;
    const char* cursor = payload + strlen(prefix);
    double values[15];
    for (int i = 0; i < 15; ++i)
    {
        char* end = nullptr;
        values[i] = strtod(cursor, &end);
        if (end == cursor || !isfinite(values[i])) return false;
        if (i < 14 && *end != ',') return false;
        if (i == 14 && *end != '*') return false;
        cursor = end + 1;
    }
    if (values[1] < 0 || values[1] > 65535 || values[1] != floor(values[1]) ||
        values[2] < 0 || values[2] > 255 || values[2] != floor(values[2]) ||
        values[3] < 0 || values[3] > 255 || values[3] != floor(values[3]) ||
        fabs(values[4]) > 90 || fabs(values[5]) > 180 ||
        values[10] < 0 || values[11] < 0 || values[12] < 0 || values[13] < 0 || values[14] < 0)
        return false;
    GNSS_Solution_LLA solution;
    solution.GpsTow = values[0]; solution.GpsWeek = static_cast<uint16_t>(values[1]);
    solution.GnssFix = static_cast<uint8_t>(values[2]); solution.NumSats = static_cast<uint8_t>(values[3]);
    solution.Lat = values[4]; solution.Lon = values[5]; solution.Alt = values[6];
    solution.VelN = values[7]; solution.VelE = values[8]; solution.VelD = values[9];
    solution.PosUncertaintyN = values[10]; solution.PosUncertaintyE = values[11];
    solution.PosUncertaintyD = values[12]; solution.GnssVelUncertainty = values[13];
    solution.GnssTimeUncertainty = values[14];
    measurement.gnssSolution = solution;
    measurement.gnssReceived = true;
    measurement.gnssReceivedAtMs = millis();
    return true;
}

void VN300Parsing::parse_INS_Solution_LLA(char* payload, VN300Measurement& measurement){
    char header[7];



    commaParser.parseLine(payload,header,

        measurement.insSolution.GpsTow,
        measurement.insSolution.GpsWeek,
        measurement.insSolution.InsStatus,

        measurement.insSolution.Yaw,
        measurement.insSolution.Pitch,
        measurement.insSolution.Roll,

        measurement.insSolution.PosLat,
        measurement.insSolution.PosLon,
        measurement.insSolution.PosAlt,

        measurement.insSolution.VelN,
        measurement.insSolution.VelE,
        measurement.insSolution.VelD,

        measurement.insSolution.AttUncertainty,
        measurement.insSolution.PosUncertainty,
        measurement.insSolution.VelUncertainty
    );
}





void VN300Parsing::parse_YPR_LinearAccel_Gyro(char* payload, VN300Measurement& measurement  )
{
    char header[7];

    commaParser.parseLine(payload,header,

//         struct YPR_LinearAccel_Gyro {
//     float Yaw;
//     float Pitch;
//     float Roll;
//     float LinAccelN;
//     float LinAccelE;
//     float LinAccelD;
//     float GyroX;
//     float GyroY;
//     float GyroZ;
// };
        measurement.yprLinearAccelGyro.Yaw,
        measurement.yprLinearAccelGyro.Pitch,
        measurement.yprLinearAccelGyro.Roll,

        measurement.yprLinearAccelGyro.LinAccelN,
        measurement.yprLinearAccelGyro.LinAccelE,
        measurement.yprLinearAccelGyro.LinAccelD,

        measurement.yprLinearAccelGyro.GyroX,
        measurement.yprLinearAccelGyro.GyroY,
        measurement.yprLinearAccelGyro.GyroZ
    );
}



#endif // VN300_PARSING_H