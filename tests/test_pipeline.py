"""单元测试：pipeline.run 编排。"""

from __future__ import annotations

from app.config import AppConfig, ChannelConfig, DigestConfig, FilterConfig, PushConfig, SourceConfig
from app.models import Digest, RawItem, RenderedDigest, Section
from app.pipeline import run


def _item(i: int) -> RawItem:
    return RawItem(
        id=f"s1:r{i}",
        source_id="s1",
        raw_id=f"r{i}",
        title=f"T{i}",
        link=f"https://x.com/{i}",
        summary=None,
        published_at=None,
        extra={},
    )


def test_pipeline_run_happy_path(monkeypatch):
    from app import pipeline as pipeline_mod

    raw = [_item(1), _item(1)]  # duplicate link after dedup should be 1

    def fake_fetch(sources, timeout_per_source=30):
        return raw

    def fake_dedup(items, key="link"):
        return [items[0]]

    def fake_filter(items, cfg):
        return items

    def fake_digest(items, cfg):
        return Digest(
            id="d1",
            title="早报",
            generated_at="2025-02-15T07:00:00+00:00",
            sections=[Section(name="All", items=items)],
            rendered=RenderedDigest(markdown="# x"),
        )

    def fake_send(digest, push_cfg):
        from app.push import ChannelResult

        return [ChannelResult(channel_type="bark", success=True)]

    monkeypatch.setattr(pipeline_mod, "fetch_all", fake_fetch)
    monkeypatch.setattr(pipeline_mod, "deduplicate", fake_dedup)
    monkeypatch.setattr(pipeline_mod, "filter_and_sort", fake_filter)
    monkeypatch.setattr(pipeline_mod, "generate_digest", fake_digest)
    monkeypatch.setattr(pipeline_mod, "send_all", fake_send)

    cfg = AppConfig(
        sources=[SourceConfig(id="s1", type="rss", url="https://example.com/feed.xml")],
        filter=FilterConfig(strategy="rule"),
        digest=DigestConfig(strategy="template"),
        push=PushConfig(channels=[ChannelConfig(type="bark", enabled=True, key="k")]),
    )

    result = run(cfg)
    assert result.ok
    assert "fetch" in result.steps_completed
    assert "dedup" in result.steps_completed
    assert "filter" in result.steps_completed
    assert "digest" in result.steps_completed
    assert "push" in result.steps_completed
    assert result.raw_count == 2
    assert result.dedup_count == 1
    assert result.filtered_count == 1
    assert result.digest is not None
    assert result.push_success_count == 1


def test_pipeline_run_filter_failure(monkeypatch):
    from app import pipeline as pipeline_mod

    monkeypatch.setattr(pipeline_mod, "fetch_all", lambda s, timeout_per_source: [_item(1)])
    monkeypatch.setattr(pipeline_mod, "deduplicate", lambda items, key="link": items)

    def boom(items, cfg):
        raise RuntimeError("agent not ready")

    monkeypatch.setattr(pipeline_mod, "filter_and_sort", boom)

    cfg = AppConfig(
        sources=[SourceConfig(id="s1", type="rss", url="https://example.com/feed.xml")],
        filter=FilterConfig(strategy="rule"),
        digest=DigestConfig(strategy="template"),
        push=PushConfig(channels=[]),
    )

    result = run(cfg)
    assert not result.ok
    assert "filter failed" in result.errors[0]
    assert result.digest is None


def test_pipeline_run_no_push_channels(monkeypatch):
    from app import pipeline as pipeline_mod

    monkeypatch.setattr(pipeline_mod, "fetch_all", lambda s, timeout_per_source: [_item(1)])
    monkeypatch.setattr(pipeline_mod, "deduplicate", lambda items, key="link": items)
    monkeypatch.setattr(pipeline_mod, "filter_and_sort", lambda items, cfg: items)
    monkeypatch.setattr(
        pipeline_mod,
        "generate_digest",
        lambda items, cfg: Digest(
            id="d",
            title="t",
            generated_at="2025-02-15T07:00:00+00:00",
            sections=[],
            rendered=RenderedDigest(markdown=""),
        ),
    )

    cfg = AppConfig(
        sources=[SourceConfig(id="s1", type="rss", url="https://example.com/feed.xml")],
        filter=FilterConfig(strategy="rule"),
        digest=DigestConfig(strategy="template"),
        push=PushConfig(channels=[]),
    )

    result = run(cfg)
    assert result.ok
    assert "push_skipped" in result.steps_completed
    assert result.channel_results == []


def test_pipeline_populates_city_weather_in_digest_extra(monkeypatch):
    from unittest.mock import patch, MagicMock
    from app import pipeline as pipeline_mod
    from app.config import WeatherConfig, CityWeatherConfig

    monkeypatch.setattr(pipeline_mod, "fetch_all", lambda s, timeout_per_source: [])
    monkeypatch.setattr(pipeline_mod, "deduplicate", lambda items, key="link": items)
    monkeypatch.setattr(pipeline_mod, "filter_and_sort", lambda items, cfg: items)
    monkeypatch.setattr(
        pipeline_mod,
        "generate_digest",
        lambda items, cfg, **kw: Digest(
            id="t", title="test", generated_at="2026-01-01T00:00:00Z",
            rendered=RenderedDigest(),
        ),
    )

    cfg = AppConfig(
        sources=[SourceConfig(id="s1", type="rss", url="https://example.com/feed.xml")],
        filter=FilterConfig(strategy="rule"),
        digest=DigestConfig(strategy="template"),
        push=PushConfig(channels=[]),
        weather=WeatherConfig(
            enabled=True,
            api_key="test",
            cities=[CityWeatherConfig(name="北京", adcode="110000", popular=True)],
        ),
    )

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.content = b"{}"
    fake_resp.text = "{}"
    fake_resp.json.return_value = {
        "city": "北京", "weather": "晴", "temperature": "22",
        "feels_like": "20", "humidity": "45", "wind_direction": "东北",
        "wind_power": "3级", "uv": "5", "aqi": "35", "aqi_category": "优",
        "hourly_forecast": [],
    }
    fake_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get = MagicMock(return_value=fake_resp)

    with patch("app.weather.httpx.Client", return_value=mock_client):
        result = run(cfg)

    assert result.digest is not None
    assert "city_weather" in result.digest.extra
    assert "北京" in result.digest.extra["city_weather"]
