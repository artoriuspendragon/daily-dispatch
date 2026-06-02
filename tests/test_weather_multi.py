"""Multi-city weather fetch tests."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from app.config import CityWeatherConfig, WeatherConfig
from app.weather import fetch_weather_multi


def _fake_response(city: str) -> dict:
    return {
        "city": city,
        "weather": "晴",
        "temperature": "22",
        "feels_like": "20",
        "humidity": "45",
        "wind_direction": "东北",
        "wind_power": "3级",
        "uv": "5",
        "aqi": "35",
        "aqi_category": "优",
        "hourly_forecast": [],
    }


def test_fetch_weather_multi_returns_dict():
    cities = [
        CityWeatherConfig(name="北京", adcode="110000", popular=True),
        CityWeatherConfig(name="上海", adcode="310000"),
    ]
    config = WeatherConfig(enabled=True, api_key="test")

    def mock_get(url, params=None, headers=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"{}"
        resp.text = "{}"
        resp.json.return_value = _fake_response(params["city"])
        resp.raise_for_status = MagicMock()
        return resp

    with patch("app.weather.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = mock_get
        mock_client_cls.return_value = mock_client

        result = fetch_weather_multi(cities, config)

    assert "北京" in result
    assert "上海" in result
    assert "城市：北京" in result["北京"]
    assert "城市：上海" in result["上海"]


def test_fetch_weather_multi_skips_failed_cities():
    cities = [
        CityWeatherConfig(name="北京", adcode="110000"),
        CityWeatherConfig(name="失败市", adcode="999999"),
    ]
    config = WeatherConfig(enabled=True)

    def mock_get(url, params=None, headers=None):
        if params["city"] == "失败市":
            raise ConnectionError("API down")
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"{}"
        resp.text = "{}"
        resp.json.return_value = _fake_response(params["city"])
        resp.raise_for_status = MagicMock()
        return resp

    with patch("app.weather.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get = mock_get
        mock_client_cls.return_value = mock_client

        result = fetch_weather_multi(cities, config)

    assert "北京" in result
    assert "失败市" not in result
