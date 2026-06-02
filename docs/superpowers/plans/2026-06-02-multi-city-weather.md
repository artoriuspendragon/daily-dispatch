# Multi-City Newspaper Weather Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show multi-city weather on the newspaper with a dropdown city selector, auto-detecting the reader's city via IP geolocation.

**Architecture:** Add configurable city list to `WeatherConfig`, fetch weather for all cities in parallel, send popular cities' raw data through one LLM call for polished descriptions, embed all city weather as JSON in the newspaper HTML, and add client-side JS for IP geolocation + dropdown switching with localStorage persistence.

**Tech Stack:** Python (httpx, pydantic), MiniMax/OpenAI-compatible LLM API, vanilla JS (IP geolocation via ip-api.com), CSS

---

### Task 1: Config — Add CityWeatherConfig and cities list

**Files:**
- Modify: `src/app/config.py:193-206`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_config.py`, add:

```python
def test_weather_cities_default():
    """WeatherConfig should have a default cities list with 15+ entries."""
    from app.config import WeatherConfig
    w = WeatherConfig(enabled=True)
    assert len(w.cities) >= 15
    popular = [c for c in w.cities if c.popular]
    assert len(popular) >= 5
    assert all(c.name and c.adcode for c in w.cities)


def test_weather_cities_custom():
    """WeatherConfig should accept a custom cities list."""
    from app.config import WeatherConfig, CityWeatherConfig
    w = WeatherConfig(
        enabled=True,
        cities=[CityWeatherConfig(name="测试市", adcode="999999", popular=True)],
    )
    assert len(w.cities) == 1
    assert w.cities[0].name == "测试市"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py::test_weather_cities_default tests/test_config.py::test_weather_cities_custom -v`
Expected: FAIL — `CityWeatherConfig` not defined

- [ ] **Step 3: Write implementation**

In `src/app/config.py`, add `CityWeatherConfig` before `WeatherConfig` (around line 193) and update `WeatherConfig`:

```python
_DEFAULT_CITIES: list[dict[str, str | bool]] = [
    {"name": "北京", "adcode": "110000", "popular": True},
    {"name": "上海", "adcode": "310000", "popular": True},
    {"name": "广州", "adcode": "440100", "popular": True},
    {"name": "深圳", "adcode": "440300", "popular": True},
    {"name": "成都", "adcode": "510100", "popular": True},
    {"name": "杭州", "adcode": "330100", "popular": True},
    {"name": "武汉", "adcode": "420100", "popular": True},
    {"name": "重庆", "adcode": "500000", "popular": True},
    {"name": "南京", "adcode": "320100"},
    {"name": "西安", "adcode": "610100"},
    {"name": "苏州", "adcode": "320500"},
    {"name": "天津", "adcode": "120000"},
    {"name": "郑州", "adcode": "410100"},
    {"name": "长沙", "adcode": "430100"},
    {"name": "东莞", "adcode": "441900"},
    {"name": "青岛", "adcode": "370200"},
    {"name": "昆明", "adcode": "530100"},
    {"name": "厦门", "adcode": "350200"},
]


class CityWeatherConfig(BaseModel):
    name: str
    adcode: str
    popular: bool = False


class WeatherConfig(BaseModel):
    """天气 API 配置。"""

    enabled: bool = False
    api_url: str = "https://uapis.cn/api/v1/misc/weather"
    api_key: Optional[str] = None
    city: str = "北京"
    adcode: str = "100085"
    schedule: Optional[str] = None
    cities: list[CityWeatherConfig] = Field(
        default_factory=lambda: [CityWeatherConfig(**c) for c in _DEFAULT_CITIES]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py::test_weather_cities_default tests/test_config.py::test_weather_cities_custom -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app/config.py tests/test_config.py
git commit -m "feat(config): add CityWeatherConfig and cities list to WeatherConfig"
```

---

### Task 2: Weather — Multi-city fetch

**Files:**
- Modify: `src/app/weather.py`
- Test: `tests/test_weather_multi.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_weather_multi.py`:

```python
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

    call_count = 0

    def mock_get(url, params=None, headers=None):
        nonlocal call_count
        call_count += 1
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_weather_multi.py -v`
Expected: FAIL — `fetch_weather_multi` not found

- [ ] **Step 3: Write implementation**

In `src/app/weather.py`, add after the existing `fetch_weather` function:

```python
def _fetch_single_city(
    city_name: str, adcode: str, config: WeatherConfig, client: httpx.Client,
) -> tuple[str, str | None]:
    """Fetch weather for one city, return (city_name, summary_or_None)."""
    params = {
        "city": city_name,
        "adcode": adcode,
        "extended": "true",
        "hourly": "true",
        "lang": "zh",
    }
    headers = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    try:
        resp = client.get(config.api_url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        summary = _build_weather_summary(data)
        logger.info("[weather] city=%s fetched ok, len=%d", city_name, len(summary))
        return city_name, summary
    except Exception as e:
        logger.warning("[weather] city=%s fetch failed: %s", city_name, e)
        return city_name, None


def fetch_weather_multi(
    cities: list, config: WeatherConfig,
) -> dict[str, str]:
    """Fetch weather for multiple cities. Returns {city_name: raw_summary} for successful fetches."""
    results: dict[str, str] = {}
    with httpx.Client(timeout=httpx.Timeout(15)) as client:
        for city in cities:
            name, summary = _fetch_single_city(city.name, city.adcode, config, client)
            if summary is not None:
                results[name] = summary
    logger.info("[weather] multi-city fetch done: %d/%d succeeded", len(results), len(cities))
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_weather_multi.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app/weather.py tests/test_weather_multi.py
git commit -m "feat(weather): add fetch_weather_multi for multi-city fetch"
```

---

### Task 3: Weather — LLM batch descriptions for popular cities

**Files:**
- Create: `src/app/weather_llm.py`
- Test: `tests/test_weather_llm.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_weather_llm.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_weather_llm.py -v`
Expected: FAIL — `app.weather_llm` not found

- [ ] **Step 3: Write implementation**

Create `src/app/weather_llm.py`:

```python
"""
Batch LLM descriptions for popular cities' weather.

One LLM call takes raw weather summaries for N cities and returns
a friendly one-paragraph description per city (no personal schedule references).
"""

from __future__ import annotations

import json
import logging
import re

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
    """Send raw weather for multiple cities to LLM, return {city: description}.

    Returns empty dict on failure (non-blocking).
    """
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_weather_llm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app/weather_llm.py tests/test_weather_llm.py
git commit -m "feat(weather): add LLM batch city weather descriptions"
```

---

### Task 4: Digest model — Add extra field

**Files:**
- Modify: `src/app/models.py:74-86`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_models.py`, add:

```python
def test_digest_extra_field():
    from app.models import Digest, RenderedDigest
    d = Digest(id="t", title="test", generated_at="2026-01-01T00:00:00Z")
    assert d.extra == {}
    d.extra["city_weather"] = {"北京": "晴"}
    assert d.extra["city_weather"]["北京"] == "晴"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py::test_digest_extra_field -v`
Expected: FAIL — `Digest` has no field `extra`

- [ ] **Step 3: Write implementation**

In `src/app/models.py`, add `extra` field to `Digest` (around line 84, after `rendered`):

```python
class Digest(BaseModel):
    id: str
    title: str
    generated_at: str
    sections: list[Section] = Field(default_factory=list)
    rendered: RenderedDigest = Field(default_factory=RenderedDigest)
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"str_strip_whitespace": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py::test_digest_extra_field -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app/models.py tests/test_models.py
git commit -m "feat(models): add extra dict field to Digest"
```

---

### Task 5: Pipeline — Wire multi-city weather fetch and LLM

**Files:**
- Modify: `src/app/pipeline.py:104-115`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_pipeline.py`, add (or find an appropriate location near existing weather tests):

```python
def test_pipeline_populates_city_weather_in_digest_extra(tmp_path):
    """When weather.enabled and weather.cities are configured, digest.extra['city_weather'] is populated."""
    from unittest.mock import patch, MagicMock
    from app.config import AppConfig, WeatherConfig, CityWeatherConfig
    from app.pipeline import run

    config = AppConfig(
        weather=WeatherConfig(
            enabled=True,
            api_key="test",
            cities=[CityWeatherConfig(name="北京", adcode="110000", popular=True)],
        ),
    )

    with patch("app.pipeline.fetch_all", return_value=[]), \
         patch("app.pipeline.deduplicate", return_value=[]), \
         patch("app.pipeline.filter_and_sort", return_value=[]), \
         patch("app.pipeline.generate_digest") as mock_digest, \
         patch("app.weather.httpx.Client") as mock_client_cls, \
         patch("app.weather_llm.generate_city_descriptions", return_value={"北京": "晴朗好天气"}):

        # Mock weather API
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"{}"
        resp.text = "{}"
        resp.json.return_value = {"city": "北京", "weather": "晴", "temperature": "22",
                                   "feels_like": "20", "humidity": "45", "wind_direction": "东北",
                                   "wind_power": "3级", "uv": "5", "aqi": "35", "aqi_category": "优",
                                   "hourly_forecast": []}
        resp.raise_for_status = MagicMock()
        mock_client.get = MagicMock(return_value=resp)
        mock_client_cls.return_value = mock_client

        # Mock digest generation
        from app.models import Digest, RenderedDigest
        mock_digest.return_value = Digest(
            id="t", title="test", generated_at="2026-01-01T00:00:00Z",
            rendered=RenderedDigest(),
        )

        result = run(config)

    assert result.digest is not None
    assert "city_weather" in result.digest.extra
    assert "北京" in result.digest.extra["city_weather"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py::test_pipeline_populates_city_weather_in_digest_extra -v`
Expected: FAIL — pipeline doesn't populate `city_weather`

- [ ] **Step 3: Write implementation**

In `src/app/pipeline.py`, modify the weather step (around line 104) to also fetch multi-city weather and run LLM:

```python
    # 4) 天气（可选，不阻断 pipeline）
    weather_summary = None
    user_schedule = None
    city_weather: dict[str, str] = {}
    if config.weather.enabled:
        try:
            from app.weather import fetch_weather, fetch_weather_multi
            weather_summary = fetch_weather(config.weather)
            user_schedule = config.weather.schedule
            result.steps_completed.append("weather")
            logger.info("pipeline weather done has_data=%s", weather_summary is not None)
        except Exception as e:
            logger.warning("pipeline weather failed: %s", e)

        # Multi-city weather for newspaper
        if config.weather.cities:
            try:
                from app.weather import fetch_weather_multi
                from app.weather_llm import generate_city_descriptions

                raw_multi = fetch_weather_multi(config.weather.cities, config.weather)

                # LLM descriptions for popular cities
                popular_raw = {
                    c.name: raw_multi[c.name]
                    for c in config.weather.cities
                    if c.popular and c.name in raw_multi
                }
                llm_descriptions: dict[str, str] = {}
                if popular_raw and config.digest.agent:
                    llm_descriptions = generate_city_descriptions(
                        popular_raw,
                        endpoint=config.digest.agent.endpoint,
                        api_key=config.digest.agent.api_key,
                        model=config.digest.agent.model,
                    )

                # Merge: LLM descriptions for popular, raw for the rest
                for city_name, raw_text in raw_multi.items():
                    city_weather[city_name] = llm_descriptions.get(city_name, raw_text)

                result.steps_completed.append("weather_multi")
                logger.info("pipeline multi-city weather done: %d cities", len(city_weather))
            except Exception as e:
                logger.warning("pipeline multi-city weather failed: %s", e)
```

Then after digest generation (around line 126, after `result.digest = digest`), add:

```python
        if city_weather:
            digest.extra["city_weather"] = city_weather
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline.py::test_pipeline_populates_city_weather_in_digest_extra -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/app/pipeline.py tests/test_pipeline.py
git commit -m "feat(pipeline): fetch multi-city weather and store in digest.extra"
```

---

### Task 6: Push/Publish — Thread city_weather to render_paper

**Files:**
- Modify: `src/app/push/webpaper.py`
- Modify: `src/app/web/publish.py`
- Modify: `src/app/web/paper.py` (just the `render_paper` signature for now)
- Test: `tests/test_webpaper.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_webpaper.py`, add:

```python
def test_publish_embeds_city_weather(tmp_path):
    d = _sample_digest()
    d.extra = {"city_weather": {"北京": "晴朗好天气", "上海": "多云转阴"}}
    out = tmp_path / "site"
    res = publish_paper(d, output_dir=str(out), git_publish=False)
    html = res.page_path.read_text(encoding="utf-8")
    assert "__weather" in html
    assert "北京" in html
    assert "晴朗好天气" in html
    assert "上海" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_webpaper.py::test_publish_embeds_city_weather -v`
Expected: FAIL — `__weather` not in HTML

- [ ] **Step 3: Write implementation**

**3a.** In `src/app/web/publish.py`, modify `publish_paper` to extract and pass `city_weather`:

Add near the top of `publish_paper`, after `date_str = _digest_date(digest)`:

```python
    city_weather = digest.extra.get("city_weather") if hasattr(digest, "extra") else None
```

Then pass `city_weather=city_weather` to both `render_paper` calls:

```python
    page_html = render_paper(
        digest, masthead_en=masthead_en, archive_href="../archive.html",
        multi_page=multi_page, show_summaries=show_summaries,
        prev_href=prev_href_dated,
        city_weather=city_weather,
    )
    ...
    index_html = render_paper(
        digest, masthead_en=masthead_en, archive_href="archive.html",
        multi_page=multi_page, show_summaries=show_summaries,
        prev_href=prev_href_index,
        city_weather=city_weather,
    )
```

**3b.** In `src/app/web/paper.py`, add `city_weather` parameter to `render_paper`:

```python
def render_paper(
    digest: Digest,
    *,
    masthead_en: str = "THE DAILY DISPATCH",
    archive_href: str = "archive.html",
    issue_label: str | None = None,
    multi_page: bool = True,
    show_summaries: bool = True,
    prev_href: str | None = None,
    city_weather: dict[str, str] | None = None,
) -> str:
```

Pass `city_weather` through to `_render_front` and `_render_single`. Also pass to `_document` to embed the JSON:

In `render_paper`, change `_document` calls to:
```python
    return _document(title, masthead_en, body, city_weather=city_weather)
```

In `_document`, add the parameter and embed JSON before `_JS`:

```python
def _document(title: str, masthead_en: str, body: str, *, city_weather: dict[str, str] | None = None) -> str:
    weather_script = ""
    if city_weather:
        import json
        cities_json = json.dumps(city_weather, ensure_ascii=False)
        default_city = next(iter(city_weather))
        weather_script = f'\n<script>var __weather={{data:{cities_json},cities:{json.dumps(list(city_weather.keys()), ensure_ascii=False)},default:"{_esc(default_city)}"}}</script>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="stage">
{body}
</div>{weather_script}
<script>{_JS}</script>
</body>
</html>
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_webpaper.py::test_publish_embeds_city_weather -v`
Expected: PASS

- [ ] **Step 5: Run existing tests to check for regressions**

Run: `python -m pytest tests/test_webpaper.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/app/web/paper.py src/app/web/publish.py tests/test_webpaper.py
git commit -m "feat(publish): thread city_weather through to HTML as embedded JSON"
```

---

### Task 7: Paper renderer — Dropdown weatherbar + city-switch JS

**Files:**
- Modify: `src/app/web/paper.py` (CSS, JS, `_render_front`, `_render_single`)
- Test: `tests/test_webpaper.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_webpaper.py`, add:

```python
def test_multipage_city_weather_dropdown():
    d = _sample_digest()
    d.extra = {"city_weather": {"北京": "晴朗好天气", "上海": "多云转阴"}}
    html = render_paper(d, multi_page=True, city_weather=d.extra["city_weather"])
    assert 'class="city-select"' in html
    assert '<option' in html
    assert "北京" in html and "上海" in html
    assert "dispatch_city" in html  # localStorage key in JS
    assert "ip-api.com" in html  # IP geolocation


def test_no_city_weather_keeps_old_weatherbar():
    html = render_paper(_sample_digest(), multi_page=True)
    assert "city-select" not in html
    assert "多云转晴" in html  # old single-line weatherbar still works
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_webpaper.py::test_multipage_city_weather_dropdown tests/test_webpaper.py::test_no_city_weather_keeps_old_weatherbar -v`
Expected: First test FAIL, second should PASS

- [ ] **Step 3: Add dropdown CSS**

In `src/app/web/paper.py`, add to `_CSS` after the existing `.weatherbar b{...}` rule:

```css
.city-select{appearance:none;-webkit-appearance:none;border:none;border-bottom:1px solid var(--muted);
  background:transparent;font-family:inherit;font-size:14px;color:var(--ink);cursor:pointer;
  padding:2px 18px 2px 4px;margin-left:8px;outline:none;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6'><path d='M0 0l5 6 5-6z' fill='%235a5347'/></svg>");
  background-repeat:no-repeat;background-position:right 4px center;background-size:8px 5px;}
.city-select:hover{border-bottom-color:var(--accent);color:var(--accent);}
.city-select:focus{border-bottom-color:var(--accent);}
.weather-text{margin-top:8px;white-space:pre-line;}
```

- [ ] **Step 4: Add city-switch JS**

In `src/app/web/paper.py`, append to `_JS` (inside the IIFE, after the parallax code, before the closing `})();`):

```javascript
  // City weather switcher
  if(typeof __weather!=='undefined'&&__weather.data){
    var wd=__weather.data,wc=__weather.cities,wdef=__weather.default;
    var sel=document.querySelector('.city-select');
    var txt=document.querySelector('.weather-text');
    if(sel&&txt){
      function setCity(c){
        if(!wd[c])c=wdef;
        sel.value=c;
        txt.textContent=wd[c];
      }
      sel.addEventListener('change',function(){
        setCity(sel.value);
        try{localStorage.setItem('dispatch_city',sel.value);}catch(e){}
      });
      // Priority: localStorage > IP geolocation > default
      var saved=null;
      try{saved=localStorage.getItem('dispatch_city');}catch(e){}
      if(saved&&wd[saved]){setCity(saved);}
      else{
        setCity(wdef);
        fetch('https://ip-api.com/json/?fields=city,regionName&lang=zh-CN')
          .then(function(r){return r.json();})
          .then(function(d){
            var loc=(d.city||'')+(d.regionName||'');
            for(var i=0;i<wc.length;i++){
              if(loc.indexOf(wc[i])>=0||wc[i].indexOf(d.city||'__')>=0){
                setCity(wc[i]);
                try{localStorage.setItem('dispatch_city',wc[i]);}catch(e){}
                break;
              }
            }
          }).catch(function(){});
      }
    }
  }
```

- [ ] **Step 5: Modify `_render_front` to render dropdown weatherbar when city_weather is available**

In `_render_front`, add `city_weather: dict[str, str] | None = None` parameter. Replace the weatherbar rendering:

```python
    wbar = ""
    if city_weather:
        options = "".join(
            f'<option value="{_esc(c)}">{_esc(c)}</option>' for c in city_weather
        )
        default_city = next(iter(city_weather))
        default_text = _esc(city_weather[default_city])
        wbar = (
            f'<div class="weatherbar"><b>今日天气</b>'
            f'<select class="city-select">{options}</select>'
            f'<div class="weather-text">{default_text}</div></div>'
        )
    elif weather and weather.text:
        wbar = f'<div class="weatherbar"><b>{_esc(weather.name)}</b>　{_esc(weather.text).splitlines()[0] if weather.text else ""}</div>'
```

Apply the same change to `_render_single` — add `city_weather=None` parameter, same `if city_weather:` / `elif weather and weather.text:` logic for `wbar`.

Thread `city_weather` from `render_paper` through to `_render_front` and `_render_single`:

In the multi-page path:
```python
    pages = [
        _render_front(
            title=title, masthead_en=masthead_en, issue=issue, dt=dt, weather=weather,
            headline=headline, index_entries=index_entries, total=total,
            archive_href=archive_href, show_summary=show_summaries,
            prev_href=prev_href, city_weather=city_weather,
        )
    ]
```

In the single-page path, pass `city_weather` to `_render_single`.

- [ ] **Step 6: Run tests to verify**

Run: `python -m pytest tests/test_webpaper.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/app/web/paper.py tests/test_webpaper.py
git commit -m "feat(paper): multi-city weather dropdown with IP geolocation and localStorage"
```

---

### Task 8: Integration — Verify full pipeline with existing tests

**Files:** None (test-only)

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 2: Fix any regressions**

If any existing tests fail, fix them. Common issues:
- `_document` signature change may break tests that call `render_paper` indirectly
- `Digest` extra field may affect snapshot/comparison tests

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: resolve test regressions from multi-city weather feature"
```
