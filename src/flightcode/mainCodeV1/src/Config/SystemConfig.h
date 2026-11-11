
#pragma once


#include "../Utilities/Utilities.h"
#include "Arduino.h"

namespace SystemConfig {

   constexpr float rover_mass = 2.0; // 

   constexpr float gravity = 9.81; // m/s^2




   static_assert(rover_mass > 0.0f, "rover_mass must be > 0");

   static_assert(gravity > 0.0f, "gravity must be > 0");


}