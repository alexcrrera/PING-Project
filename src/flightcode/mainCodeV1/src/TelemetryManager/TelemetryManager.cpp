#include "TelemetryManager.h"

#include "../FlightManager/FlightManager.h"


namespace
{
    using TelemetryUtilities::addTelemetryField;

    void appendATVLFields(String& payload, const LanderState& state)
    {
        const auto& data = state.group_ATVL_data;
        addTelemetryField(payload, data.BODY_velocity_X_SI, 2);
        addTelemetryField(payload, data.BODY_velocity_Y_SI, 2);
        addTelemetryField(payload, data.yaw_DEG, 2);
        addTelemetryField(payload, data.pitch_DEG, 2);
        addTelemetryField(payload, data.roll_DEG, 2);
    }

    void appendWSSTFields(String& payload, const LanderState& state)
    {
        const auto& data = state.group_WSST_data;
        addTelemetryField(payload, data.RPM_FL);
        addTelemetryField(payload, data.RPM_FR);
        addTelemetryField(payload, data.RPM_RL);
        addTelemetryField(payload, data.RPM_RR);
        addTelemetryField(payload, data.estimated_slip_ratio_FL, 3);
        addTelemetryField(payload, data.estimated_slip_ratio_FR, 3);
        addTelemetryField(payload, data.estimated_slip_ratio_RL, 3);
        addTelemetryField(payload, data.estimated_slip_ratio_RR, 3);
    }

    void appendACCLFields(String& payload, const LanderState& state)
    {
        const auto& data = state.group_ACCL_data;
        addTelemetryField(payload, data.BODY_linear_acceleration_X_SI, 2);
        addTelemetryField(payload, data.BODY_linear_acceleration_Y_SI, 2);
        addTelemetryField(payload, data.BODY_linear_acceleration_Z_SI, 2);
    }

    void appendGPDFields(String& payload, const LanderState& state)
    {
        const auto& data = state.group_GPS_data;
        addTelemetryField(payload, static_cast<int>(data.isValid));
        addTelemetryField(payload, data.numSats);
        addTelemetryField(payload, data.latitude_deg, 7);
        addTelemetryField(payload, data.longitude_deg, 7);
        addTelemetryField(payload, data.altitude_ellipsoid_m, 2);
        addTelemetryField(payload, data.velN, 3);
        addTelemetryField(payload, data.velE, 3);
        addTelemetryField(payload, data.velD, 3);
        addTelemetryField(payload, data.horizontalUncertainty_m, 2);
        addTelemetryField(payload, data.velocityUncertainty_mps, 2);
    }

    void appendGMBLFields(String& payload, const LanderState& state)
    {
        const auto& data = state.group_GMBL_data;
        addTelemetryField(payload, data.estimated_horizontal_distance_1_M, 2);
        addTelemetryField(payload, data.estimated_horizontal_distance_2_M, 2);
        addTelemetryField(payload, data.estimation_validity);
        addTelemetryField(payload, data.gimbal_mode);
        addTelemetryField(payload, data.lidar_distance_M, 2);
        addTelemetryField(payload, data.pan_angle_DEG, 2);
        addTelemetryField(payload, data.tilt_angle_DEG, 2);
    }

    void appendWGDFields(String& payload, const LanderState& state)
    {
        const auto& data = state.wheel_data;
        const WheelData* wheels[] = {
            &data.front_left, &data.front_right, &data.rear_left, &data.rear_right
        };

        for (const auto* wheel : wheels)
        {
            addTelemetryField(payload, wheel->RPM);
            addTelemetryField(payload, wheel->current_A, 2);
            addTelemetryField(payload, wheel->estimated_torque_NM, 2);
            addTelemetryField(payload, wheel->estimated_slip_ratio, 3);
        }
    }
}

TelemetryManager::TelemetryManager(
    FlightManager* flightManager
)
    : flightManager(flightManager),
      groups{
          {ATVL::config, appendATVLFields},
          {WSST::config, appendWSSTFields},
          {ACCL::config, appendACCLFields},
          {GPD::config, appendGPDFields},
          {GMBL::config, appendGMBLFields},
          {WGD::config, appendWGDFields},
          {CommsConfig::RGM, nullptr}
      }
{
}


// ============================================================
// BEGIN
// ============================================================

void TelemetryManager::begin()
{

    send_USB_String("INIT START OF TELEM",true);

    for (auto& group : groups)
    {
        group.handler.begin(group.config.frequency, this, &TelemetryManager::send_group, &group);
    }

    if (CommsConfig::USB.enabled)
    {
        
        USB_output_initialized = true;
      

        Serial.begin(CommsConfig::USB.baudrate); // Initialize USB serial port

        send_USB_String("INIT SERIAL OK",true);

        //USB_output_handler.begin(CommsConfig::USB.frequency, this, &TelemetryManager::send_USB_String);
        
    }


    if (CommsConfig::RADIO.enabled)
    {
        
       
        CommsConfig::RADIO.port->begin(CommsConfig::RADIO.baudrate);
        RADIO_output_initialized = true;
        //RADIO_output_handler.begin(CommsConfig::RADIO.frequency, this, &TelemetryManager::send_RADIO_String);   

        send_RADIO_String("INIT RADIO OK",true);
    }
    if (CommsConfig::CONTROLLER.enabled)
    {
        CONTROLLER_port->begin(CommsConfig::CONTROLLER.baudrate);
        CONTROLLER_output_initialized = true;
        send_CONTROLLER_String("INIT CONTROLLER OK", true);
    }

}


void TelemetryManager::send_group(const GroupEntry* group)
{
    const auto& config = group->config;
    const bool sendUSB = config.enabled_for_USB &&
        (USB_output_type == SerialOutputType::GROUP_FORMAT ||
         (group == &groups[6] && USB_output_type == SerialOutputType::BASE_STATION_FORMAT)) &&
        USB_output_enabled && USB_output_initialized && USB_periodic_output_enabled;
    const bool sendRadio = config.enabled_for_RADIO &&
        RADIO_output_type == SerialOutputType::GROUP_FORMAT &&
        RADIO_output_enabled && RADIO_output_initialized && RADIO_periodic_output_enabled;

    const bool sendController = config.enabled_for_CONTROLLER &&
        CONTROLLER_output_type == SerialOutputType::GROUP_FORMAT &&
        CONTROLLER_output_enabled && CONTROLLER_output_initialized && CONTROLLER_periodic_output_enabled;

    if (!sendUSB && !sendRadio && !sendController)
    {
        return;
    }

    String payload = CommsConfig::outputHeaderTelemetryFormat;
    payload += ",";
    payload += config.name;
    if (group->appendFields)
    {
        group->appendFields(payload, flightManager->getLander().getState());
    }
    else
    {
        const auto regime = flightManager->getStateMachine().getCurrentFlightRegimeData();
        addTelemetryField(payload, flightManager->getStateMachine().getStateAsString());
        addTelemetryField(payload, static_cast<int>(regime.isDynamic));
        addTelemetryField(payload, regime.max_horizontal_velocity_ms, 2);
        addTelemetryField(payload, regime.max_horizontal_acceleration_ms2, 2);
        addTelemetryField(payload, regime.max_yaw_velocity_degs, 2);
        addTelemetryField(payload, regime.max_yaw_acceleration_degs2, 2);
        addTelemetryField(payload, regime.pitch_roll_abort_angle_deg, 2);
        addTelemetryField(payload, regime.yaw_abort_angle_deg, 2);
        addTelemetryField(payload, regime.min_thrust_percentage, 1);
        addTelemetryField(payload, regime.max_thrust_percentage, 1);
    }
    payload += CommsConfig::outputLineEndingTelemetryFormat;

    if (sendUSB)
    {
        send_USB_String(payload, true);
    }
    if (sendRadio)
    {
        send_RADIO_String(payload, true);
    }
    if (sendController)
    {
        send_CONTROLLER_String(payload, true);
    }
}


void TelemetryManager::update(uint32_t now)
{
    handleInput();

    for (auto& group : groups)
    {
        group.handler.handle();
    }

    // --------------------------------------------------------
    // USB
    // --------------------------------------------------------
    if (USB_output_initialized && USB_periodic_output_enabled)
    {



    if (now - USB_last_output_time >=static_cast<uint32_t>(1000.0f / CommsConfig::USB.frequency)){
        
        USB_last_output_time = now;


        if (USB_output_enabled)
        {
            if (USB_output_type ==SerialOutputType::HUMAN_READABLE)
            {
                send_USB_String(get_debug_payload(),false);
            }
            else if (USB_output_type == SerialOutputType::BASE_STATION_FORMAT)
            {
                send_USB_String(get_telemetry_payload(),false);
            }
        }
    }
}


    // --------------------------------------------------------
    // RADIO
    // --------------------------------------------------------

    if (RADIO_periodic_output_enabled && (now - RADIO_last_output_time >= static_cast<uint32_t>(1000.0f / CommsConfig::RADIO.frequency)))
    {
        RADIO_last_output_time = now;


        if (RADIO_output_enabled)
        {
           
            if (RADIO_output_type ==SerialOutputType::HUMAN_READABLE){
                
                send_RADIO_String(get_debug_payload(),false);
            }

            if (RADIO_output_type ==SerialOutputType::BASE_STATION_FORMAT){
                
                send_RADIO_String(get_telemetry_payload(),false);
            }
        }
    }

    if (CONTROLLER_output_initialized && CONTROLLER_periodic_output_enabled &&
        now - CONTROLLER_last_output_time >= static_cast<uint32_t>(1000.0f / CommsConfig::CONTROLLER.frequency))
    {
        CONTROLLER_last_output_time = now;
        if (CONTROLLER_output_enabled)
        {
            if (CONTROLLER_output_type == SerialOutputType::HUMAN_READABLE)
                send_CONTROLLER_String(get_debug_payload(), false);
            else if (CONTROLLER_output_type == SerialOutputType::BASE_STATION_FORMAT)
                send_CONTROLLER_String(get_telemetry_payload(), false);
        }
    }
}

// ============================================================
// UPDATE
// ============================================================
void TelemetryManager::handleInput()
{
    if (USB_input_enabled)
    {
        handle_USB_input();
    }

    if (RADIO_input_enabled && RADIO_output_initialized)
    {
        handle_RADIO_input();
    }

    if (CONTROLLER_input_enabled && CONTROLLER_output_initialized)
    {
        handle_CONTROLLER_input();
    }
}

void TelemetryManager::handle_USB_input()
{
    while (Serial.available() > 0)
    {
        char incomingChar = Serial.read();

        if (incomingChar == '\n' || incomingChar == '\r')
        {
            if (dataIndexUSB > 0)
            {
                incomingDataUSB[dataIndexUSB] = '\0'; // Null-terminate the string
                String incomingText = String(incomingDataUSB);
                flightManager->getCommandHandler().consumeIncomingCommand(incomingText);
                dataIndexUSB = 0; // Reset index for next command
            }
        }
        else
        {
            if (dataIndexUSB < bufferSizeUSB - 1)
            {
                incomingDataUSB[dataIndexUSB++] = incomingChar;
            }
            if (dataIndexUSB >= bufferSizeUSB - 1)
            {
                // Buffer overflow, reset index
                dataIndexUSB = 0;
            }
        }
    }
}

void TelemetryManager::handle_RADIO_input()
{
    while (RADIO_port->available() > 0)
    {
        char incomingChar = RADIO_port->read();

        if (incomingChar == '\n' || incomingChar == '\r')
        {
            if (dataIndexRADIO > 0)
            {
                incomingDataRADIO[dataIndexRADIO] = '\0'; // Null-terminate the string
                String incomingText = String(incomingDataRADIO);
                flightManager->getCommandHandler().consumeIncomingCommand(incomingText);
                dataIndexRADIO = 0; // Reset index for next command
            }
        }
        else
        {
            if (dataIndexRADIO < bufferSizeRADIO - 1)
            {
                incomingDataRADIO[dataIndexRADIO++] = incomingChar;
            }
            if (dataIndexRADIO >= bufferSizeRADIO - 1)
            {
                // Buffer overflow, reset index
                dataIndexRADIO = 0;
            }
        }
    }
}

void TelemetryManager::handle_CONTROLLER_input()
{
    while (CONTROLLER_port->available() > 0)
    {
        char incomingChar = CONTROLLER_port->read();
        if (incomingChar == '\n' || incomingChar == '\r')
        {
            if (!controllerInputOverflow && dataIndexCONTROLLER > 0)
            {
                incomingDataCONTROLLER[dataIndexCONTROLLER] = '\0';
                flightManager->getCommandHandler().consumeIncomingCommand(String(incomingDataCONTROLLER));
            }
            dataIndexCONTROLLER = 0;
            controllerInputOverflow = false;
        }
        else if (!controllerInputOverflow)
        {
            if (dataIndexCONTROLLER < CommsConfig::CONTROLLER.bufferSize - 1)
                incomingDataCONTROLLER[dataIndexCONTROLLER++] = incomingChar;
            else
                controllerInputOverflow = true;
        }
    }
}

void TelemetryManager::send_CONTROLLER_String(const String& content, bool jumpToNextLine)
{
    if (!CONTROLLER_output_enabled || !CONTROLLER_output_initialized) return;
    CONTROLLER_port->print(content);
    if (jumpToNextLine) CONTROLLER_port->print("\n");
}

void TelemetryManager::toggle_CONTROLLER(bool enable)
{
    CONTROLLER_output_enabled = CONTROLLER_output_initialized && enable;
}

void TelemetryManager::toggle_CONTROLLER_periodic()
{
    if (CONTROLLER_output_initialized)
        CONTROLLER_periodic_output_enabled = !CONTROLLER_periodic_output_enabled;
}

void TelemetryManager::send_RADIO_String(const String& content,bool jumpToNextLine)
{
    
    if(!RADIO_output_enabled || !RADIO_output_initialized){
        return;
    }

    RADIO_port->print(content);

    if (jumpToNextLine)
    {
        RADIO_port->print("\n");
    }
}

void TelemetryManager::send_USB_String(const String& content,bool jumpToNextLine)
{

    if(!USB_output_enabled || !USB_output_initialized){
        return;
    }

    USB_port->print(content);


    if (jumpToNextLine)
    {
        USB_port->print("\n");
    }
}

void TelemetryManager::toggle_RADIO(bool enable)
{
    if (!RADIO_output_initialized)
    {
        RADIO_output_enabled = false;
        return;
    }

    RADIO_output_enabled = enable;
}

void TelemetryManager::toggle_USB_periodic()
{
    if (!USB_output_initialized)
    {
        USB_output_enabled = false;
        Serial.println("USB output not initialized, cannot toggle.");
        return;
    }

    USB_periodic_output_enabled = !USB_periodic_output_enabled;
}

void TelemetryManager::toggle_RADIO_periodic()
{
    if (!RADIO_output_initialized)
    {
        RADIO_output_enabled = false;
        Serial.println("RADIO output not initialized, cannot toggle.");
        return;
    }

    RADIO_periodic_output_enabled = !RADIO_periodic_output_enabled;
}

void TelemetryManager::toggle_USB(bool enable)
{
    if (!USB_output_initialized)
    {
        USB_output_enabled = false;
        return;
    }

    USB_output_enabled = enable;
}

void TelemetryManager::toggle_USB()
{
    if (!USB_output_initialized)
    {
        USB_output_enabled = false;
        return;
    }

    USB_output_enabled = !USB_output_enabled;
}
