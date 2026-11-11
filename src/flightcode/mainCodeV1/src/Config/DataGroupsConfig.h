#pragma once

struct GroupConfig {
    const char* name;
    float frequency; // Hz
    bool enabled_for_USB = false;
    bool enabled_for_RADIO = true;
    bool enabled_for_CONTROLLER = false;
};

namespace CommsConfig {

    inline constexpr GroupConfig ATVL = {
        .name = "ATVL",
        .frequency = 15.0f,
        .enabled_for_USB = false,
        .enabled_for_RADIO = true,
        .enabled_for_CONTROLLER = false
    };

    inline constexpr GroupConfig WSST = {
        .name = "WSST",
        .frequency = 5.0f,
        .enabled_for_USB = false,
        .enabled_for_RADIO = true,
        .enabled_for_CONTROLLER = false
    };

    inline constexpr GroupConfig ACCL = {
        .name = "ACCL",
        .frequency = 5.0f,
        .enabled_for_USB = false,
        .enabled_for_RADIO = true,
        .enabled_for_CONTROLLER = false
    };

    inline constexpr GroupConfig GPD = {
        .name = "GPD",
        .frequency = 2.0f,
        .enabled_for_USB = false,
        .enabled_for_RADIO = true,
        .enabled_for_CONTROLLER = false
    };

    inline constexpr GroupConfig GMBL = {
        .name = "GMBL",
        .frequency = 0.5f,
        .enabled_for_USB = false,
        .enabled_for_RADIO = true,
        .enabled_for_CONTROLLER = false
    };

    inline constexpr GroupConfig WGD = {
        .name = "WGD",
        .frequency = 0.5f,
        .enabled_for_USB = false,
        .enabled_for_RADIO = false,
        .enabled_for_CONTROLLER = false
    };

}
