#include "FlightGuard.h"


String FlightGuard::motorEnabledStatus() const{
    String status = (overrideFlags.EDF_enabled) ? "[ON]" : "[OFF]";    
    return(status);
}



String FlightGuard::motorSafetyStatus() const{
    String status = (overrideFlags.EDF_armed) ? "[ARMED]" : "[DISARMED]";    
    return(status);
}



String FlightGuard::getFlightGuardStatus() const{
    String status = "FlightGuard Status:\n";
    status += "EDF Enabled: " + String(overrideFlags.EDF_enabled) + "\n";
    status += "EDF Armed: " + String(overrideFlags.EDF_armed) + "\n";
    status += "TVC Enabled: " + String(overrideFlags.TVC_enabled) + "\n";
    status += "Horizontal Overspeed OK: " + String(overrideFlags.horizontal_overspeed_ok) + "\n";
    status += "Roll/Pitch OK: " + String(overrideFlags.roll_pitch_ok) + "\n";
    status += "Yaw OK: " + String(overrideFlags.yaw_ok) + "\n";
    return status;
}