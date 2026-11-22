#include "VN300.h"


#include <math.h>

#include "VN300_parsing.h"

#include <string.h>

VN300::VN300()
    : vectornav(nullptr),
      commaParser(",")
{
}


bool VN300::begin()


    {
    Serial.println("INITIALIZING VECTORNAV");
    delay(100); // wait for the serial port to initialize
    vectornav = SensorConfig::VN300.port;

   

    vectornav->begin(SensorConfig::VN300.baudrate);
      delay(400); // wait for the serial port to initialize    
    // Register 240:
    // Yaw / Pitch / Roll
    // Linear acceleration NED
    // Compensated angular rates



    // YPR NED -> 17, BODY -> 16
    vectornav->println(VN300Utilities::configureAsynchOutputType(16));
         delay(500); // wait for the serial port to initialize
    // Asynchronous output frequency
    vectornav->println(VN300Utilities::configureAsynchOutputFrequency(SensorConfig::YBA_LinearAccel_Gyro_poll_frequency));


    dataIndex = 0;
    
    delay(400); // wait for the serial port to initialize
  
    // polls solutions at the specified rates
    //YPR_LinearAccel_Gyro_poll_handler.begin(SensorConfig::YPR_LinearAccel_Gyro_poll_frequency,[this]() { poll_YPR_LinearAccel_Gyro(); }); // set to automatic output from VN300, no need to poll
   GNSS_Solution_LLA_poll_handler.begin(SensorConfig::GNSS_Solution_LLA_poll_frequency,this,&VN300::poll_GNSS_Solution_LLA);

INS_Solution_LLA_poll_handler.begin(
    SensorConfig::INS_Solution_LLA_poll_frequency,
    this,
    &VN300::poll_INS_Solution_LLA
);

    return true;
}




void VN300::update()
{
    // YPR Linear Accel Gyro is set to automatic output from VN300, no need to poll
    GNSS_Solution_LLA_poll_handler.handle();
    INS_Solution_LLA_poll_handler.handle();

    manage_incoming_data(); // read one byte at a time
   

}


void VN300::process_data()
{   

  
    int vectornavIdentity = VN300Utilities::getHeader(incomingData);

    switch (vectornavIdentity)
    {

      
        case 1:
        {
           break;}

        case 58: // GNS Solution LLA
        {
            VN300Parsing::parse_GNSS_Solution_LLA(incomingData, measurement_data);
            break;}

        case 63: //  INSSolution-LLA
        {
            VN300Parsing::parse_INS_Solution_LLA(incomingData, measurement_data);
            break;}


        case 240: // Yaw / Pitch / Roll, Linear Acceleration, Compensated Angular Rates
        {
            VN300Parsing::parse_YPR_LinearAccel_Gyro(incomingData, measurement_data);
            
            break;}



        case 239: // Yaw / Pitch / Roll, Linear Acceleration in Body Frame, Compensated Angular Rates
        { 
            VN300Parsing::parse_YBA_LinearAccel_Gyro(incomingData, measurement_data);
            measurement_data.attitudeReceived = true;
            measurement_data.attitudeReceivedAtMs = millis();
          
            break;}

        default:
            break;
    }
}






void VN300::manage_incoming_data(){
    // reads one byte at a time from the serial port 
    // and processes it when a newline character is received

    while (vectornav->available() > 0)
    {
        const char incomingChar = vectornav->read();

        if (incomingChar == '\n')
        {
            incomingData[dataIndex] = '\0';

            Serial.print("VN300 incoming data: " );
            Serial.println(incomingData);
            process_data();

            dataIndex = 0;

            continue;
        }

        if (incomingChar == '\r')
        {
            continue;
        }

        if (dataIndex >= bufferSize - 1) //  overflow protection
        {
            dataIndex = 0;
        }

        incomingData[dataIndex] = incomingChar;
        dataIndex++;
    }
}




void VN300::poll_GNSS_Solution_LLA()
{
    if(!SensorConfig::enable_GNSS_Solution_LLA_polling) {
        return; // polling is disabled
    }
    vectornav->println(VN300Utilities::get_cmd_poll_GNSS_Solution_LLA());
}
void VN300::poll_INS_Solution_LLA()
{
    if(!SensorConfig::enable_INS_Solution_LLA_polling) {
        return; // polling is disabled
    }
    vectornav->println(VN300Utilities::get_cmd_poll_INS_Solution_LLA());
}
void VN300::poll_YPR_LinearAccel_Gyro()
{

    if(!SensorConfig::enable_YPR_LinearAccel_Gyro_polling) {
        return; // polling is disabled
    }
    vectornav->println(VN300Utilities::get_cmd_poll_YPR_LinearAccel_Gyro());
}


VN300Measurement& VN300::getMeasurement()
{
    return measurement_data;
}