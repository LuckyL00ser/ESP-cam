#include "photo_uploader.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "app_config.h"
#include "esp_camera.h"
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "time_sync.h"

static const char *TAG = "photo_uploader";

static const char *BOUNDARY = "----esp-cam-boundary";
static const char *CAPTURE_STARTED_FIELD = "capture_started_at";
static const char *CAPTURE_FINISHED_FIELD = "capture_finished_at";

typedef struct {
    const char *capture_started_at;
    const char *capture_finished_at;
} capture_times_t;

static int64_t frame_sensor_age_ms(const camera_fb_t *fb)
{
    if (fb == NULL) {
        return -1;
    }

    int64_t frame_us = (int64_t)fb->timestamp.tv_sec * 1000000LL + (int64_t)fb->timestamp.tv_usec;
    int64_t now_us = esp_timer_get_time();
    if (now_us < frame_us) {
        return 0;
    }
    return (now_us - frame_us) / 1000;
}

static void discard_stale_frames(void)
{
    for (int i = 0; i < 2; i++) {
        camera_fb_t *fb = esp_camera_fb_get();
        if (fb == NULL) {
            break;
        }
        esp_camera_fb_return(fb);
    }
}

static int append_text_field(char *buf, size_t buf_size, size_t offset, const char *field_name, const char *value)
{
    return snprintf(
        buf + offset,
        buf_size - offset,
        "--%s\r\n"
        "Content-Disposition: form-data; name=\"%s\"\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "%s\r\n",
        BOUNDARY,
        field_name,
        value);
}

static esp_err_t upload_jpeg(const uint8_t *jpeg_data, size_t jpeg_len, const capture_times_t *times)
{
    esp_http_client_config_t config = {
        .url = APP_UPLOAD_URL,
        .method = HTTP_METHOD_POST,
        .crt_bundle_attach = esp_crt_bundle_attach,
        .timeout_ms = 30000,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (client == NULL) {
        return ESP_FAIL;
    }

    char content_type[96];
    snprintf(content_type, sizeof(content_type), "multipart/form-data; boundary=%s", BOUNDARY);

    char header_buf[512];
    int started_part_len = append_text_field(header_buf, sizeof(header_buf), 0, CAPTURE_STARTED_FIELD, times->capture_started_at);
    if (started_part_len <= 0) {
        esp_http_client_cleanup(client);
        return ESP_ERR_INVALID_ARG;
    }

    int finished_part_len = append_text_field(
        header_buf, sizeof(header_buf), (size_t)started_part_len, CAPTURE_FINISHED_FIELD, times->capture_finished_at);
    if (finished_part_len <= 0) {
        esp_http_client_cleanup(client);
        return ESP_ERR_INVALID_ARG;
    }

    int headers_len = started_part_len + finished_part_len;

    char image_part_header[256];
    int image_part_header_len = snprintf(
        image_part_header,
        sizeof(image_part_header),
        "--%s\r\n"
        "Content-Disposition: form-data; name=\"%s\"; filename=\"capture.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n"
        "\r\n",
        BOUNDARY,
        APP_UPLOAD_FIELD_NAME);

    char part_footer[48];
    int part_footer_len = snprintf(part_footer, sizeof(part_footer), "\r\n--%s--\r\n", BOUNDARY);

    if (image_part_header_len <= 0 || part_footer_len <= 0) {
        esp_http_client_cleanup(client);
        return ESP_ERR_INVALID_ARG;
    }

    size_t body_len = (size_t)headers_len + (size_t)image_part_header_len + jpeg_len + (size_t)part_footer_len;
    char *body = malloc(body_len);
    if (body == NULL) {
        esp_http_client_cleanup(client);
        return ESP_ERR_NO_MEM;
    }

    size_t offset = 0;
    memcpy(body + offset, header_buf, (size_t)headers_len);
    offset += (size_t)headers_len;
    memcpy(body + offset, image_part_header, (size_t)image_part_header_len);
    offset += (size_t)image_part_header_len;
    memcpy(body + offset, jpeg_data, jpeg_len);
    offset += jpeg_len;
    memcpy(body + offset, part_footer, (size_t)part_footer_len);

    esp_http_client_set_header(client, "Content-Type", content_type);
    esp_http_client_set_post_field(client, body, body_len);

    esp_err_t err = esp_http_client_perform(client);
    if (err == ESP_OK) {
        int status = esp_http_client_get_status_code(client);
        ESP_LOGI(
            TAG,
            "Upload HTTP status: %d (started=%s finished=%s)",
            status,
            times->capture_started_at,
            times->capture_finished_at);
        if (status < 200 || status >= 300) {
            err = ESP_FAIL;
        }
    } else {
        ESP_LOGE(TAG, "Upload failed: %s", esp_err_to_name(err));
    }

    free(body);
    esp_http_client_cleanup(client);
    return err;
}

static void upload_task(void *arg)
{
    (void)arg;

    while (true) {
        discard_stale_frames();

        char capture_started_at[32] = {0};
        if (!time_sync_format_now_iso(capture_started_at, sizeof(capture_started_at))) {
            ESP_LOGE(TAG, "Clock not synced; skipping capture cycle");
            vTaskDelay(pdMS_TO_TICKS(APP_CAPTURE_INTERVAL_MS));
            continue;
        }

        camera_fb_t *fb = esp_camera_fb_get();

        char capture_finished_at[32] = {0};
        if (!time_sync_format_now_iso(capture_finished_at, sizeof(capture_finished_at))) {
            ESP_LOGE(TAG, "Clock not synced after capture; dropping frame");
            if (fb != NULL) {
                esp_camera_fb_return(fb);
            }
            vTaskDelay(pdMS_TO_TICKS(APP_CAPTURE_INTERVAL_MS));
            continue;
        }

        if (fb == NULL) {
            ESP_LOGE(TAG, "Capture failed (started=%s)", capture_started_at);
            vTaskDelay(pdMS_TO_TICKS(APP_CAPTURE_INTERVAL_MS));
            continue;
        }

        int64_t sensor_age_ms = frame_sensor_age_ms(fb);
        capture_times_t times = {
            .capture_started_at = capture_started_at,
            .capture_finished_at = capture_finished_at,
        };

        ESP_LOGI(
            TAG,
            "Captured %ux%u JPEG (%u bytes) started=%s finished=%s sensor_age=%lldms",
            fb->width,
            fb->height,
            fb->len,
            capture_started_at,
            capture_finished_at,
            (long long)sensor_age_ms);

        esp_err_t err = upload_jpeg(fb->buf, fb->len, &times);
        esp_camera_fb_return(fb);

        if (err == ESP_OK) {
            ESP_LOGI(TAG, "Upload succeeded");
        }

        vTaskDelay(pdMS_TO_TICKS(APP_CAPTURE_INTERVAL_MS));
    }
}

esp_err_t photo_uploader_start(void)
{
    BaseType_t ok = xTaskCreate(upload_task, "photo_uploader", 10240, NULL, 5, NULL);
    return ok == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
