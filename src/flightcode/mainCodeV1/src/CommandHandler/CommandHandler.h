#pragma once


#include <Arduino.h>

#include "../Utilities/Utilities.h"

#include <TextParser.h>

class FlightManager;

struct RoverDriveInput
{
    float throttle = 0.0f;
    float steering = 0.0f;
    float leftX = 0.0f;
    float leftY = 0.0f;
    float leftTrigger = 0.0f;
    float rightTrigger = 0.0f;
    float cameraPan = 0.0f;
    float cameraTilt = 0.0f;
    bool brake = true;
    uint32_t lastDriveTime = 0;
    uint32_t lastStickTime = 0;
    uint32_t lastLeftTime = 0;
    uint32_t lastTriggerTime = 0;
    bool received = false;
};





class CommandHandler {
public:
    CommandHandler() = default;
    void begin(FlightManager* flight_manager_);

    void consumeIncomingCommand(String incomingText);

    RoverDriveInput getDriveInput() const;
    const String& getLastButton() const { return lastButton; }
    uint32_t getButtonSequence() const { return buttonSequence; }

    void setOKFeedback(const String& message) {command_feedback = "[OK]: " + message;}
    void setErrorFeedback(const String& error) {command_feedback = "[ERROR]: " + error;}
    void setFeedback(const String& feedback) {command_feedback = feedback;}
    void setFeedback(const String &header, const String& message) {command_feedback = "["+ header +"]:" + message;}

    String command_feedback = "[CLEAR]"; // default feedback message, can be updated after processing a command


private: 
    void parseCommand(String header, String payload);
    FlightManager* flight_manager = nullptr;
    RoverDriveInput driveInput;
    String lastButton;
    uint32_t buttonSequence = 0;


   
   // TextParser textParser;
};

