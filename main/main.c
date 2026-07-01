#include "app_config.h"
#include "camera_manager.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "photo_uploader.h"
#include "time_sync.h"
#include "wifi_manager.h"

static const char *TAG = "esp_cam";

void app_main(void)
{
    ESP_LOGI(TAG, "ESP32-S3 camera uploader starting");

    ESP_ERROR_CHECK(wifi_manager_init());
    ESP_ERROR_CHECK(wifi_manager_wait_connected(portMAX_DELAY));

    esp_err_t time_err = time_sync_init_and_wait();
    if (time_err != ESP_OK) {
        ESP_LOGW(TAG, "Continuing without reliable wall clock; uploads may be skipped");
    }

    ESP_ERROR_CHECK(camera_manager_init());
    ESP_ERROR_CHECK(photo_uploader_start());

    ESP_LOGI(TAG, "Running (interval: %d ms, upload: %s)", APP_CAPTURE_INTERVAL_MS, APP_UPLOAD_URL);
}
