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
你是天气播报员。给定若干城市的天气数据，为每个城市写一段简短的天气描述（2-3句，约80字）。
要求：
- 客观、亲切、自然，适合报纸天气栏目
- 包含：天气状况、气温、体感建议（穿衣/带伞等）
- 不要提及任何个人作息或时间表
- 严格输出一个 JSON 对象，key 为城市名，value 为描述字符串
- 不要输出任何解释文字或代码块标记
"""


def generate_city_descriptions(
    raw_weather: dict[str, str],
    *,
    endpoint: str,
    api_key: str,
    model: str,
    timeout_seconds: int = 60,
    max_tokens: int = 4096,
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
