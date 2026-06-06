"""LLM 工具（function calling）的 schema 定义。

在这里新增一个工具，下一次请求时 LLM 就能用它——无需改动其他任何代码
（编排器 IntentOrchestrator._dispatch 里再补上对应的执行分支即可）。
"""

# 注：下方 description 是发给 LLM 的功能性字段，保持英文以贴合多数模型的训练语料，
# 各工具的中文释义见每个工具上方的注释。
TOOLS: list[dict] = [
    # set_device_state：开关某个智能家电，或修改其参数（亮度/温度/模式等）
    {
        "type": "function",
        "function": {
            "name": "set_device_state",
            "description": "Turn a smart appliance on or off, or change its parameters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Identifier such as light_livingroom, ac_livingroom.",
                    },
                    "state": {
                        "type": "string",
                        "enum": ["on", "off", "open", "closed"],
                    },
                    "brightness": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "temperature": {
                        "type": "integer",
                        "minimum": 16,
                        "maximum": 30,
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["cool", "heat", "fan", "dry"],
                    },
                },
                "required": ["device_id"],
            },
        },
    },
    # list_devices：列出所有已知家电及其当前状态
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "List all known smart appliances and their current state.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # router_reboot：整机重启家庭路由器（破坏性操作，需先经用户确认）
    {
        "type": "function",
        "function": {
            "name": "router_reboot",
            "description": "Reboot the home router. Requires user confirmation first.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # router_restart_wifi：仅重启路由器 WiFi 射频，不整机重启
    {
        "type": "function",
        "function": {
            "name": "router_restart_wifi",
            "description": "Restart the WiFi radio on the home router without rebooting it.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


SYSTEM_PROMPT = """你是一个家庭智能助理，负责把用户的中文口语指令翻译成对智能设备的操作。

可用工具已经通过 function calling 暴露。请遵守以下原则：
1. 能用工具完成的指令必须调用工具，不要只回复文字。
2. 对涉及网络/路由器的破坏性操作（如 router_reboot），先用普通文字向用户确认，得到肯定答复后再调用工具。
3. 如果用户没有指明具体设备，但只有一个候选设备，可以直接选它；否则反问澄清。
4. 回复语言保持简洁，一两句话即可，方便 TTS 播报。
"""
