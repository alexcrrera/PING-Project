#pragma once


enum class STATE_MACHINE_STATES {
    AWAIT, // the rover is waiting in idle mode
    
    NAVIGATION_TRACTION,
    NAVIGATION_NO_TRACTION, // the rover does not control the traction, but is still in navigation mode
    NAVIGATION_OBSTACLE, // the rover is in obstacle mode - reduced velocity 

    FULLBRAKE, // the rover is in full brake mode, which means that the motors are braking and the rover is not moving

    ABORT // rover is in abort mode
};


