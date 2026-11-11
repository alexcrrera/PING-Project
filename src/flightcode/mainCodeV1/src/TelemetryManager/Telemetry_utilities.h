#pragma once

#include <Arduino.h>
#include <type_traits>

#include "../Utilities/Utilities.h"

#include "../Config/FlightRegimeConfig.h"

#include "../Config/CommsConfig.h"


namespace TelemetryUtilities
{
    void addDebugTitle(String& payload, const String& title);

    void addDebugGroup(String& payload, const String& name);
    void addDebugGroup(String& payload, const NED_coordinates& NED_payload, const String& name);
    void addDebugGroup(String& payload, const BODY_coordinates& BODY_payload, const String& name);
    void addDebugGroup(String& payload, const Rotation_Euler_coordinates& Euler_payload, const String& name);

    void addDebugField(String& payload, const String& name, const String& value);
    void addDebugField(String& payload, const String& name, float value);
    void addDebugField(String& payload, const String& name, bool value);

    template <typename T>
    inline void addTelemetryField(String& payload, T value, int decimals = -1)
    {
    if (payload.length() > 0)
        payload += ",";

    if constexpr (std::is_same_v<T, bool>)
        payload += value ? "[OK]" : "[X]";
    else if constexpr (std::is_same_v<T, String>)
        payload += value;
    else if (decimals >= 0)
        payload += String(value, decimals);
    else
        payload += String(value, CommsConfig::decimalsAllowed_telemetry);
    }

    void addTelemetryGroup(String& payload, const NED_coordinates& NED_payload);
    void addTelemetryGroup(String& payload, const BODY_coordinates& BODY_payload);
    void addTelemetryGroup(String& payload, const Rotation_Euler_coordinates& Euler_payload);

        bool isGroupEnabled(const String& group_name);

        String getGroupPayload(const String& group_name);

    String getGroup1_asString();
    String getGroup2_asString();
    String getGroup3_asString();
    String getGroupFlags_asString();
    String getGroupLowPriority_asString();

    String getGroupContent(const String& group_name);




    String getFlightRegimeDataAsString(const FlightRegimeData& regime_data);
}