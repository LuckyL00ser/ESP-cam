#include "time_sync.h"

#include <sys/time.h>
#include <time.h>

#include "esp_log.h"
#include "esp_sntp.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "time_sync";

static bool s_time_valid = false;

static void sntp_sync_notification(struct timeval *tv)
{
    (void)tv;
    s_time_valid = true;
    ESP_LOGI(TAG, "SNTP time synchronized");
}

esp_err_t time_sync_init_and_wait(void)
{
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_set_time_sync_notification_cb(sntp_sync_notification);
    esp_sntp_init();

    for (int attempt = 0; attempt < 30; ++attempt) {
        if (esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED) {
            s_time_valid = true;
            ESP_LOGI(TAG, "Time ready");
            return ESP_OK;
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }

    struct tm timeinfo = {0};
    time_t now = 0;
    time(&now);
    gmtime_r(&now, &timeinfo);
    if (timeinfo.tm_year >= (2020 - 1900)) {
        s_time_valid = true;
        ESP_LOGI(TAG, "Time looks valid");
        return ESP_OK;
    }

    ESP_LOGW(TAG, "SNTP sync timed out");
    return ESP_ERR_TIMEOUT;
}

bool time_sync_is_valid(void)
{
    if (esp_sntp_get_sync_status() == SNTP_SYNC_STATUS_COMPLETED) {
        s_time_valid = true;
    }
    return s_time_valid;
}

bool time_sync_format_now_iso(char *buf, size_t buf_len)
{
    if (buf == NULL || buf_len < 25) {
        return false;
    }

    struct timeval tv = {0};
    gettimeofday(&tv, NULL);

    struct tm tm_utc = {0};
    if (gmtime_r(&tv.tv_sec, &tm_utc) == NULL) {
        return false;
    }

    if (tm_utc.tm_year < (2020 - 1900)) {
        return false;
    }

    int written = snprintf(
        buf,
        buf_len,
        "%04d-%02d-%02dT%02d:%02d:%02d.%03ldZ",
        tm_utc.tm_year + 1900,
        tm_utc.tm_mon + 1,
        tm_utc.tm_mday,
        tm_utc.tm_hour,
        tm_utc.tm_min,
        tm_utc.tm_sec,
        tv.tv_usec / 1000);

    return written > 0 && (size_t)written < buf_len;
}
