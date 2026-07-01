#include "camera_manager.h"

#include "app_config.h"
#include "camera_pins.h"
#include "esp_camera.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "camera_manager";

static camera_config_t s_camera_config = {
    .pin_pwdn = PWDN_GPIO_NUM,
    .pin_reset = RESET_GPIO_NUM,
    .pin_xclk = XCLK_GPIO_NUM,
    .pin_sccb_sda = SIOD_GPIO_NUM,
    .pin_sccb_scl = SIOC_GPIO_NUM,
    .pin_d7 = Y9_GPIO_NUM,
    .pin_d6 = Y8_GPIO_NUM,
    .pin_d5 = Y7_GPIO_NUM,
    .pin_d4 = Y6_GPIO_NUM,
    .pin_d3 = Y5_GPIO_NUM,
    .pin_d2 = Y4_GPIO_NUM,
    .pin_d1 = Y3_GPIO_NUM,
    .pin_d0 = Y2_GPIO_NUM,
    .pin_vsync = VSYNC_GPIO_NUM,
    .pin_href = HREF_GPIO_NUM,
    .pin_pclk = PCLK_GPIO_NUM,
    .xclk_freq_hz = 20000000,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = PIXFORMAT_JPEG,
    .frame_size = FRAMESIZE_SVGA,
    .jpeg_quality = 12,
    .fb_count = 2,
    .fb_location = CAMERA_FB_IN_PSRAM,
    // LATEST keeps replacing queued frames while we wait between uploads.
    // WHEN_EMPTY freezes the first fb_count frames for the whole interval.
    .grab_mode = CAMERA_GRAB_LATEST,
};

static const char *wb_mode_name(int mode)
{
    switch (mode) {
    case 0: return "auto";
    case 1: return "sunny";
    case 2: return "cloudy";
    case 3: return "office";
    case 4: return "home";
    default: return "unknown";
    }
}

static void camera_manager_warmup_frames(int count)
{
    for (int i = 0; i < count; i++) {
        camera_fb_t *frame = esp_camera_fb_get();
        if (frame != NULL) {
            esp_camera_fb_return(frame);
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

static void camera_manager_apply_tuning(void)
{
    sensor_t *sensor = esp_camera_sensor_get();
    if (sensor == NULL) {
        ESP_LOGW(TAG, "Sensor handle unavailable; skipping color tuning");
        return;
    }

    const int wb_mode = CONFIG_APP_CAMERA_WB_MODE_VALUE;

    sensor->set_whitebal(sensor, 1);
    sensor->set_awb_gain(sensor, 1);
    if (sensor->set_wb_mode(sensor, wb_mode) != 0) {
        ESP_LOGW(TAG, "Failed to set white balance mode %d", wb_mode);
    } else {
        ESP_LOGI(TAG, "White balance preset: %s (%d)", wb_mode_name(wb_mode), wb_mode);
    }

    // Let AWB settle before the first upload.
    camera_manager_warmup_frames(5);
}

esp_err_t camera_manager_init(void)
{
    esp_err_t err = esp_camera_init(&s_camera_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed: %s", esp_err_to_name(err));
        return err;
    }

    vTaskDelay(pdMS_TO_TICKS(2000));
    camera_manager_apply_tuning();
    ESP_LOGI(TAG, "Camera initialized");
    return ESP_OK;
}
