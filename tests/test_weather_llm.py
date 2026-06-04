"""Weather LLM batch description tests."""

from __future__ import annotations

import json
from unittest.mock import patch

from app.weather_llm import generate_city_descriptions


def test_generate_city_descriptions_parses_response():
    raw_weather = {
        "北京": "城市：北京\n当前天气：晴，气温 22°C",
        "上海": "城市：上海\n当前天气：多云，气温 25°C",
    }
    fake_llm_response = json.dumps({
        "北京": "晴朗宜出行，气温22°C，东北风轻拂。",
        "上海": "多云天气，气温25°C，午后可能转阴。",
    }, ensure_ascii=False)

    with patch("app.weather_llm.call_minimax_chat", return_value=fake_llm_response):
        result = generate_city_descriptions(
            raw_weather,
            endpoint="http://test",
            api_key="test-key",
            model="test-model",
        )

    assert result["北京"] == "晴朗宜出行，气温22°C，东北风轻拂。"
    assert result["上海"] == "多云天气，气温25°C，午后可能转阴。"


def test_generate_city_descriptions_returns_empty_on_failure():
    raw_weather = {"北京": "城市：北京\n晴"}

    with patch("app.weather_llm.call_minimax_chat", side_effect=Exception("LLM down")):
        result = generate_city_descriptions(
            raw_weather,
            endpoint="http://test",
            api_key="key",
            model="model",
        )

    assert result == {}
