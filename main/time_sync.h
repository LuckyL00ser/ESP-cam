#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "esp_err.h"

esp_err_t time_sync_init_and_wait(void);
bool time_sync_is_valid(void);

/** Format current UTC wall-clock time. Returns false if clock is unsynced. */
bool time_sync_format_now_iso(char *buf, size_t buf_len);
