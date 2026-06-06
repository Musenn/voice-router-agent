// ESP32-S3「按住说话」麦克风节点固件：
// 按住按钮 → 经 I2S 从 INMP441 采集 16kHz/16bit/单声道 PCM → 通过 WebSocket
// 流式发往中枢服务 → 松开按钮发送 stop，等待下一次按键。
#include <Arduino.h>
#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include <WiFi.h>
#include <driver/i2s.h>

#include "config.h"

namespace {

constexpr i2s_port_t I2S_PORT = I2S_NUM_0;  // 使用 I2S 控制器 0 采集麦克风
WebSocketsClient ws;
volatile bool g_streaming = false;       // 是否正在录音并发送
volatile bool g_button_down = false;     // 按钮当前是否按下（去抖后）
volatile bool g_button_changed = false;  // 中断置位：按钮电平发生变化
unsigned long g_last_debounce_ms = 0;    // 上次去抖时间戳
int16_t g_frame_buf[FRAME_SAMPLES];      // 一帧 PCM 缓冲

// 按键中断服务程序：只置标志位，真正处理放到 loop 里（ISR 要尽量短）
void IRAM_ATTR onButtonChange() {
    g_button_changed = true;
}

// 设置板载 RGB 状态灯颜色（STATUS_LED_PIN < 0 时为空操作）
void setStatusLed(uint8_t r, uint8_t g, uint8_t b) {
#if STATUS_LED_PIN >= 0
    neopixelWrite(STATUS_LED_PIN, r, g, b);
#else
    (void)r; (void)g; (void)b;  // 未配置状态灯，避免「未使用参数」告警
#endif
}

// 配置 I2S 为主机接收模式，从 INMP441 读取数据
void configureI2S() {
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);  // 主机 + 接收
    cfg.sample_rate = SAMPLE_RATE_HZ;
    cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;  // INMP441 在 32 位槽内输出 24 位数据
    cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;   // 只取左声道（L/R 接 GND）
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

// 读取一帧并把 32 位采样降为 int16，写入 g_frame_buf
bool readFrameAsInt16() {
    // INMP441 把 24 位数据放在 32 位槽的高位。这里右移 14 位降采样到 int16
    // （相当于左对齐后取高 16 位附近，兼顾音量）。
    static int32_t raw[FRAME_SAMPLES];
    size_t bytes_read = 0;
    esp_err_t err = i2s_read(I2S_PORT, raw, sizeof(raw), &bytes_read, pdMS_TO_TICKS(100));
    if (err != ESP_OK || bytes_read == 0) {
        return false;  // 读取失败或无数据
    }
    size_t samples = bytes_read / sizeof(int32_t);
    for (size_t i = 0; i < samples; ++i) {
        g_frame_buf[i] = (int16_t)(raw[i] >> 14);  // 32 位 → 16 位
    }
    // 不足一帧的部分补零
    for (size_t i = samples; i < FRAME_SAMPLES; ++i) {
        g_frame_buf[i] = 0;
    }
    return true;
}

// 连接 WiFi，连上前一直阻塞重试
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

// 发送 start 事件：告知服务端采样率与编码格式，开始一轮录音
void sendStartEvent() {
    StaticJsonDocument<128> doc;
    doc["event"] = "start";
    doc["sample_rate"] = SAMPLE_RATE_HZ;
    doc["format"] = "pcm_s16le";
    char out[128];
    size_t n = serializeJson(doc, out, sizeof(out));
    ws.sendTXT(out, n);
}

// 发送 stop 事件：通知服务端本轮音频结束、开始处理
void sendStopEvent() {
    ws.sendTXT("{\"event\":\"stop\"}");
}

// WebSocket 事件回调：用状态灯颜色直观反映连接状态
void onWsEvent(WStype_t type, uint8_t* payload, size_t length) {
    switch (type) {
        case WStype_CONNECTED:
            Serial.println("ws connected");
            setStatusLed(0, 8, 0);  // 绿：已连接
            break;
        case WStype_DISCONNECTED:
            Serial.println("ws disconnected");
            setStatusLed(8, 0, 0);  // 红：断开
            break;
        case WStype_TEXT:
            Serial.printf("ws < %.*s\n", (int)length, payload);
            break;
        case WStype_BIN:
            // 服务端回传的 TTS MP3：本固件暂不播放（见 firmware/README）
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

    // 按钮接内部上拉，按下为低电平；电平变化触发中断
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), onButtonChange, CHANGE);

    setStatusLed(0, 0, 8);  // 蓝：启动中
    configureI2S();
    connectWifi();

    // 连接中枢的 WebSocket，断开后每 2 秒自动重连
    ws.begin(HUB_HOST, HUB_PORT, HUB_WS_PATH);
    ws.onEvent(onWsEvent);
    ws.setReconnectInterval(2000);
}

void loop() {
    ws.loop();  // 驱动 WebSocket 收发与重连

    // 处理按钮事件（带 30ms 去抖）
    if (g_button_changed) {
        unsigned long now = millis();
        if (now - g_last_debounce_ms > 30) {
            bool down = digitalRead(BUTTON_PIN) == LOW;
            g_last_debounce_ms = now;
            g_button_changed = false;
            if (down != g_button_down) {  // 仅在状态真正翻转时处理
                g_button_down = down;
                if (down && !g_streaming && ws.isConnected()) {
                    // 按下：开始录音
                    g_streaming = true;
                    sendStartEvent();
                    setStatusLed(16, 0, 0);  // 红：录音中
                    Serial.println("recording…");
                } else if (!down && g_streaming) {
                    // 松开：结束并发送
                    g_streaming = false;
                    sendStopEvent();
                    setStatusLed(0, 8, 0);   // 绿：空闲/已连接
                    Serial.println("…sent");
                }
            }
        }
    }

    // 录音中：持续读帧并以二进制发往服务端；空闲则短暂让出 CPU
    if (g_streaming && ws.isConnected()) {
        if (readFrameAsInt16()) {
            ws.sendBIN((uint8_t*)g_frame_buf, sizeof(g_frame_buf));
        }
    } else {
        delay(2);
    }
}
