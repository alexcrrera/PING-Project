
#include "src/FlightManager/FlightManager.h"


FlightManager ROVER;


void setup()
{
    ROVER.begin();
}


void loop()
{
    ROVER.update();
}