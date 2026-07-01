#pragma once

#include "freertos/FreeRTOS.h"

#include "esp_err.h"

esp_err_t wifi_manager_init(void);
esp_err_t wifi_manager_wait_connected(TickType_t timeout_ticks);
