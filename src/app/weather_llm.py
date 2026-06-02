"""
Batch LLM descriptions for popular cities' weather.

One LLM call takes raw weather summaries for N cities and returns
a friendly one-paragraph description per city (no personal schedule references).
"""

from __future__ import annotations

import logging

from app.agent import call_minimax_chat, extract_json_object

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是报纸天气栏目编辑。给定若干城市的天气原始数据（含逐时预报和生活指数），为每个城市写一段实用的天气播报。

## 格式要求（每个城市）
用换行分段，包含以下内容：
1. 第一行：今日概况（天气变化趋势 + 气温范围 + 一句话总结）
2. 🌅 早晨（~8:00）：气温、体感、穿衣建议、是否需要带伞/防晒
3. ☀️ 中午（~12:00）：气温变化、外出注意事项
4. 🌇 傍晚（~18:00）：气温回落情况、是否需要加衣
5. 🌙 夜间（~21:00）：夜间天气、温差提醒
6. 最后一行：生活指数亮点（如有），如洗车、运动、过敏等值得提醒的

## 风格要求
- 亲切自然，像朋友提醒你出门注意事项
- 具体实用：说"穿薄外套"而不是"注意保暖"，说"涂防晒霜"而不是"注意防晒"
- 不要提及"用户作息"或"上班/下班"等个人时间表，只说"上午""中午""傍晚"
- 每个城市约 150-250 字

## 输出格式
严格输出一个 JSON 对象，key 为城市名，value 为描述字符串（用 \\n 换行）。
不要输出任何解释文字或代码块标记。
"""


def generate_city_descriptions(
    raw_weather: dict[str, str],
    *,
    endpoint: str,
    api_key: str,
    model: str,
    timeout_seconds: int = 300,
    max_tokens: int = 8192,
) -> dict[str, str]:
    if not raw_weather:
        return {}

    user_content = "以下是各城市的天气数据，请为每个城市生成描述：\n\n"
    for city, data in raw_weather.items():
        user_content += f"### {city}\n{data}\n\n"

    try:
        text = call_minimax_chat(
            endpoint=endpoint,
            api_key=api_key,
            model=model,
            system_name=_SYSTEM_PROMPT,
            user_name="天气编辑",
            user_content=user_content,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
        data = extract_json_object(text)
        result = {}
        for city in raw_weather:
            if city in data and isinstance(data[city], str):
                result[city] = data[city].strip()
        logger.info("[weather_llm] generated descriptions for %d/%d cities", len(result), len(raw_weather))
        return result
    except Exception as e:
        logger.warning("[weather_llm] LLM call failed, returning empty: %s", e)
        return {}
