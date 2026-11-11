#include "CommandHandler.h"


void CommandHandler::begin(FlightManager* flight_manager_){
    flight_manager = flight_manager_;
}






void CommandHandler::consumeIncomingCommand(String incomingText) {
   // format "IDENTIFIER: payload1,payload2...\n"
    // Split the incoming text into identifier and payload
    int separatorIndex = incomingText.indexOf(':');
    if (separatorIndex == -1) {
        // Handle error: invalid format
        Serial.println("Invalid command format: " + incomingText);
            return;
    }

    String identifier = incomingText.substring(0, separatorIndex);
    String payload = incomingText.substring(separatorIndex + 1);

    parseCommand(identifier, payload);

    
}
RoverDriveInput CommandHandler::getDriveInput() const
{
    RoverDriveInput result = driveInput;
    if (!result.received || millis() - result.lastDriveTime > 500)
    {
        result.throttle = 0.0f;
        result.steering = 0.0f;
        result.leftX = 0.0f;
        result.leftY = 0.0f;
        result.leftTrigger = 0.0f;
        result.rightTrigger = 0.0f;
        result.cameraPan = 0.0f;
        result.cameraTilt = 0.0f;
        result.brake = true;
    }
    if (millis() - result.lastStickTime > 500)
        result.cameraPan = result.cameraTilt = 0.0f;
    if (millis() - result.lastLeftTime > 500)
        result.leftX = result.leftY = 0.0f;
    if (millis() - result.lastTriggerTime > 500)
        result.leftTrigger = result.rightTrigger = 0.0f;
    return result;
}
