#include "StateMachine.h"
#include "../FlightManager/FlightManager.h"


String StateMachine::getStateAsString() const{
    return getStateAsString(current_state);
}



String StateMachine::getStateAsString(STATE_MACHINE_STATES state) const{
    switch (state) {
        case STATE_MACHINE_STATES::AWAIT:
            return "AWAIT";

        case STATE_MACHINE_STATES::NAVIGATION_TRACTION:
            return "NAVIGATION_TRACTION";
        
        case STATE_MACHINE_STATES::NAVIGATION_NO_TRACTION:
            return "NAVIGATION_NO_TRACTION";
        
        case STATE_MACHINE_STATES::NAVIGATION_OBSTACLE:
            return "NAVIGATION_OBSTACLE";
        
        case STATE_MACHINE_STATES::FULLBRAKE:
            return "FULLBRAKE";
        

        case STATE_MACHINE_STATES::ABORT:
            return "ABORT";

       
        default:
            return "UNKNOWN STATE";
    }
}






void StateMachine::begin(FlightManager* flight_manager_){
    // initialize the state machine with a pointer to the flight manager
    flight_manager = flight_manager_;
    current_state = STATE_MACHINE_STATES::AWAIT; // set the initial state to AWAIT, which is the state where the lander is waiting for a command to take off
}

void StateMachine::update(){

    if(isDynamic(current_state)){
        flight_manager->getFlightGuard().overrideFlags.EDF_enabled = true;
        flight_manager->getFlightGuard().overrideFlags.TVC_enabled = true;
    }
    else{
        flight_manager->getFlightGuard().overrideFlags.EDF_enabled = false;
        flight_manager->getFlightGuard().overrideFlags.TVC_enabled = false;
    }
}








STATE_MACHINE_STATES StateMachine::getState() const{
    return(current_state);
}


void StateMachine::requestStateChange(STATE_MACHINE_STATES new_state){

    if(new_state == current_state){
        return;
    }
    
    if(verifyChange(new_state)){
        setState(new_state);
        auto& command_handler = flight_manager->getCommandHandler();
        command_handler.setOKFeedback(getStateAsString());
        return;
    }

    else{
        auto& command_handler = flight_manager->getCommandHandler();
        command_handler.setErrorFeedback("NO: " + getStateAsString(new_state));
        return;
    }
}


bool StateMachine::verifyChange(STATE_MACHINE_STATES new_state){

// This function can be used to request a state change, but the actual state change will be handled by the flight manager based on the current state and conditions
    // For now, we will just set the state directly
    if(new_state == STATE_MACHINE_STATES::ABORT){
        return true;
    }


    return true;
}


void StateMachine::setState(STATE_MACHINE_STATES new_state){
    current_state = new_state;
}




bool StateMachine::isDynamic(STATE_MACHINE_STATES state)const {
    return ( state == STATE_MACHINE_STATES::NAVIGATION_TRACTION ||
             state == STATE_MACHINE_STATES::NAVIGATION_NO_TRACTION ||
             state == STATE_MACHINE_STATES::NAVIGATION_OBSTACLE );
}


FlightRegimeData StateMachine::getCurrentFlightRegimeData() const {
    
    switch(current_state){


        case STATE_MACHINE_STATES::NAVIGATION_TRACTION:
            return FlightRegimeConfig::NAVIGATION_TRACTION;

        case STATE_MACHINE_STATES::NAVIGATION_NO_TRACTION:
            return FlightRegimeConfig::NAVIGATION_NO_TRACTION;

        case STATE_MACHINE_STATES::NAVIGATION_OBSTACLE:
            return FlightRegimeConfig::NAVIGATION_OBSTACLE;


        case STATE_MACHINE_STATES::AWAIT:
            return FlightRegimeConfig::FULLBRAKE;
        
        case STATE_MACHINE_STATES::FULLBRAKE:
            return FlightRegimeConfig::FULLBRAKE;

        
        case STATE_MACHINE_STATES::ABORT:
            return FlightRegimeConfig::FULLBRAKE;

        default:
            return FlightRegimeConfig::FULLBRAKE;
    }
}



