#include <Arduino.h>
#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include <WiFi.h>
#include <driver/i2s.h>

#include "config.h"

namespace {

constexpr i2s_port_t I2S_PORT = I2S_NUM_0;
WebSocketsClient ws;
volatile bool g_streaming = false;
volatile bool g_button_down = false;
volatile bool g_button_changed = false;
unsigned long g_last_debounce_ms = 0;
int16_t g_frame_buf[FRAME_SAMPLES];

void IRAM_ATTR onButtonChange() {
    g_button_changed = true;
}

void setStatusLed(uint8_t r, uint8_t g, uint8_t b) {
#if STATUS_LED_PIN >= 0
    neopixelWrite(STATUS_LED_PIN, r, g, b);
#else
    (void)r; (void)g; (void)b;
#endif
}

void configureI2S() {
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
    cfg.sample_rate = SAMPLE_RATE_HZ;
    cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
    cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
    cfg.dma_buf_count = 6;
    cfg.dma_buf_len = FRAME_SAMPLES;
    cfg.use_apll = false;
    cfg.tx_desc_auto_clear = false;
    cfg.fixed_mclk = 0;

    i2s_pin_config_t pins = {};
    pins.bck_io_num = I2S_BCLK_PIN;
    pins.ws_io_num = I2S_LRCLK_PIN;
    pins.data_in_num = I2S_DIN_PIN;
    pins.data_out_num = I2S_PIN_NO_CHANGE;

    i2s_driver_install(I2S_PORT, &cfg, 0, nullptr);
    i2s_set_pin(I2S_PORT, &pins);
    i2s_zero_dma_buffer(I2S_PORT);
}

bool readFrameAsInt16() {
    // INMP441 outputs 24-bit data in the top of a 32-bit slot. We left-align
    // and downshift to int16.
    static int32_t raw[FRAME_SAMPLES];
    size_t bytes_read = 0;
    esp_err_t err = i2s_read(I2S_PORT, raw, sizeof(raw), &bytes_read, pdMS_TO_TICKS(100));
    if (err != ESP_OK || bytes_read == 0) {
        return false;
    }
    size_t samples = bytes_read / sizeof(int32_t);
    for (size_t i = 0; i < samples; ++i) {
        g_frame_buf[i] = (int16_t)(raw[i] >> 14);
    }
    for (size_t i = samples; i < FRAME_SAMPLES; ++i) {
        g_frame_buf[i] = 0;
    }
    return true;
}

void connectWifi() {
    Serial.printf("WiFi: connecting to %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    setStatusLed(8, 8, 0);
    while (WiFi.status() != WL_CONNECTED) {
        delay(250);
        Serial.print(".");
    }
    Serial.printf("\nWiFi ok, ip=%s\n", WiFi.localIP().toString().c_str());
}

void sendStartEvent() {
    StaticJsonDocument<128> doc;
    doc["event"] = "start";
    doc["sample_rate"] = SAMPLE_RATE_HZ;
    doc["format"] = "pcm_s16le";
    char out[128];
    size_t n = serializeJson(doc, out, sizeof(out));
    ws.sendTXT(out, n);
}

void sendStopEvent() {
    ws.sendTXT("{\"event\":\"stop\"}");
}

void onWsEvent(WStype_t type, uint8_t* payload, size_t length) {
    switch (type) {
        case WStype_CONNECTED:
            Serial.println("ws connected");
            setStatusLed(0, 8, 0);
            break;
        case WStype_DISCONNECTED:
            Serial.println("ws disconnected");
            setStatusLed(8, 0, 0);
            break;
        case WStype_TEXT:
            Serial.printf("ws < %.*s\n", (int)length, payload);
            break;
        case WStype_BIN:
            Serial.printf("ws bin %u bytes\n", (unsigned)length);
            break;
        default:
            break;
    }
}

}  // namespace

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("voice-router-agent firmware boot");

    pinMode(BUTTON_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), onButtonChange, CHANGE);

    setStatusLed(0, 0, 8);
    configureI2S();
    connectWifi();

    ws.begin(HUB_HOST, HUB_PORT, HUB_WS_PATH);
    ws.onEvent(onWsEvent);
    ws.setReconnectInterval(2000);
}

void loop() {
    ws.loop();

    if (g_button_changed) {
        unsigned long now = millis();
        if (now - g_last_debounce_ms > 30) {
            bool down = digitalRead(BUTTON_PIN) == LOW;
            g_last_debounce_ms = now;
            g_button_changed = false;
            if (down != g_button_down) {
                g_button_down = down;
                if (down && !g_streaming && ws.isConnected()) {
                    g_streaming = true;
                    sendStartEvent();
                    setStatusLed(16, 0, 0);
                    Serial.println("recording…");
                } else if (!down && g_streaming) {
                    g_streaming = false;
                    sendStopEvent();
                    setStatusLed(0, 8, 0);
                    Serial.println("…sent");
                }
            }
        }
    }

    if (g_streaming && ws.isConnected()) {
        if (readFrameAsInt16()) {
            ws.sendBIN((uint8_t*)g_frame_buf, sizeof(g_frame_buf));
        }
    } else {
        delay(2);
    }
}
