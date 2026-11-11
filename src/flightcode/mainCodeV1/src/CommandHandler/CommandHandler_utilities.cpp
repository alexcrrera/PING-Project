
#include "Arduino.h"
#include "../Utilities/Utilities.h"
#include "CommandHandler.h"
#include "../FlightManager/FlightManager.h"

    void CommandHandler::parseCommand(String header, String payload)
{
    Serial.println("Command received: " + header + " with payload: " + payload + "|");

    

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