
#include "Arduino.h"
#include <math.h>
#include <stdlib.h>
#include "../Utilities/Utilities.h"
#include "CommandHandler.h"
#include "../FlightManager/FlightManager.h"

    void CommandHandler::parseCommand(String header, String payload)
{
    if (header != "DRIVE" && header != "STICK" && header != "LEFT" && header != "TRIG")
        Serial.println("Command received: " + header + " with payload: " + payload + "|");

    

    if (header == "DRIVE" || header == "STICK" || header == "LEFT" || header == "TRIG")
    {
        const char* input = payload.c_str();
        char* end = nullptr;
        const float first = strtof(input, &end);
        if (end == input || *end != ',')
            return;
        input = end + 1;
        const float second = strtof(input, &end);
        if (end == input || !isfinite(first) || !isfinite(second) ||
            first < -1.0f || first > 1.0f || second < -1.0f || second > 1.0f)
            return;
        if (header == "LEFT" || header == "TRIG")
        {
            if (*end != '\0' || (header == "TRIG" && (first < 0.0f || second < 0.0f)))
                return;
            if (header == "LEFT")
            {
                driveInput.leftX = first;
                driveInput.leftY = second;
                driveInput.lastLeftTime = millis();
            }
            else
            {
                driveInput.leftTrigger = first;
                driveInput.rightTrigger = second;
                driveInput.lastTriggerTime = millis();
            }
            return;
        }
        if (header == "STICK")
        {
            if (*end != '\0')
                return;
            driveInput.cameraPan = first;
            driveInput.cameraTilt = second;
            driveInput.lastStickTime = millis();
            return;
        }
        if (*end != ',' || (end[1] != '0' && end[1] != '1') || end[2] != '\0')
            return;
        driveInput.throttle = first;
        driveInput.steering = second;
        driveInput.brake = end[1] == '1';
        driveInput.lastDriveTime = millis();
        driveInput.received = true;
        return;
    }

    if (header == "BUTTON")
    {
        if (payload.length() > 0 && payload.length() <= 16)
        {
            lastButton = payload;
            ++buttonSequence;
            if (payload == "CROSS")
                flight_manager->getGimbal().home();
        }
        return;
    }

    if (header == "NAV_MODE")
    {
        auto& stateMachine = flight_manager->getStateMachine();
        const auto current = stateMachine.getState();
        if (payload.length() != 1 || payload[0] < '0' || payload[0] > '2')
        {
            setErrorFeedback("Invalid navigation mode");
            return;
        }
        if (current != STATE_MACHINE_STATES::AWAIT && !stateMachine.isDynamic(current))
        {
            setErrorFeedback("Navigation mode unavailable");
            return;
        }
        constexpr STATE_MACHINE_STATES modes[] = {
            STATE_MACHINE_STATES::NAVIGATION_TRACTION,
            STATE_MACHINE_STATES::NAVIGATION_NO_TRACTION,
            STATE_MACHINE_STATES::NAVIGATION_OBSTACLE
        };
        stateMachine.requestStateChange(modes[payload[0] - '0']);
        return;
    }

    if (header == "GIMBAL_MODE")
    {
        if (payload.length() != 1 || payload[0] < '0' || payload[0] > '2' ||
            !flight_manager->getGimbal().setMode(static_cast<GimbalMode>(payload[0] - '0')))
            setErrorFeedback("Invalid gimbal mode");
        else
            setOKFeedback(header);
        return;
    }

    if (header == "GIMBAL_AIM" || header == "GIMBAL_NUDGE")
    {
        const char* input = payload.c_str();
        char* end = nullptr;
        float pan = strtof(input, &end);
        if (end == input || *end != ',')
        {
            setErrorFeedback("Invalid gimbal angles");
            return;
        }
        input = end + 1;
        float tilt = strtof(input, &end);
        if (header == "GIMBAL_NUDGE" && isfinite(pan) && isfinite(tilt))
        {
            auto& gimbal = flight_manager->getGimbal();
            pan += gimbal.getPan_deg();
            tilt += gimbal.getTilt_deg();
        }
        if (end == input || *end != '\0' || !isfinite(pan) || !isfinite(tilt) ||
            !flight_manager->getGimbal().setAngles(pan, tilt))
            setErrorFeedback("Invalid gimbal angles");
        else
            setOKFeedback(header);
        return;
    }

    if (header == "GIMBAL_HOME")
    {
        if (flight_manager->getGimbal().home())
            setOKFeedback(header);
        else
            setErrorFeedback("Gimbal reset unavailable");
        return;
    }

    if(header == "YAW_ZERO"){
        setOKFeedback(header);
        Serial.println("Yaw zero command received");
        auto& state_estimator = flight_manager->getLander().getStateEstimator();
        auto& state = state_estimator.getState();
       
        state_estimator.yawZeroOffset = -state.attitude.Yaw_SI; // set yaw zero offset to current yaw
        return;
    }

    if(header == "DISARM_SERVOS"){
        setOKFeedback(header);
      
        flight_manager->getFlightGuard().overrideFlags.TVC_enabled = !flight_manager->getFlightGuard().overrideFlags.TVC_enabled;
        
        return;
    }

    if(header == "DISARM_MOTORS"){
        setOKFeedback(header);
        Serial.println("Disarm motors command received");
        flight_manager->getFlightGuard().overrideFlags.EDF_armed = false;
        return;
    }
    

    if(header == "ARM_MOTORS"){
        setOKFeedback(header);
        Serial.println("Arm motors command received");
        flight_manager->getFlightGuard().overrideFlags.EDF_armed = true;
        return;
    }
    



    if (header == "LINE"){
        setOKFeedback(header);
        flight_manager->getTelemetryManager().send_USB_debug_payload();
        
        return;
    }

    
    if (header == "TGL_USB_PER") // Toggle RADIO output periodic
    {
        setOKFeedback(header);
        Serial.println("Toggle USB output periodic command received");
        flight_manager->getTelemetryManager().toggle_USB_periodic();
        return;
    }



    if (header == "ARM")
    {
        setOKFeedback(header);
        Serial.println("Arm command received");
        return;
    }

    if (header == "TGL_RAD_PER") // Toggle RADIO output periodic
    {
        setOKFeedback(header);
        Serial.println("Toggle RADIO output periodic command received");
        flight_manager->getTelemetryManager().toggle_RADIO_periodic();
        return;
    }

    if (header == "TGL_CTRL_PER")
    {
        setOKFeedback(header);
        flight_manager->getTelemetryManager().toggle_CONTROLLER_periodic();
        return;
    }

    if (header == "DISARM")
    {
        setOKFeedback(header);
        Serial.println("Disarm command received");
        return;
    }


  


    if (header == "RESET")
    {
        setOKFeedback(header);
        Serial.println("Reset command received");
        return;
    }

    setFeedback("UNK",header);
    Serial.println("Unknown command received: " + header);
}
