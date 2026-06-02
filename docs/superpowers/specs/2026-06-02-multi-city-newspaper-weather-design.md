# Multi-City Newspaper Weather

## Problem

The email channel has personalized weather (one city + user schedule recommendations). The newspaper is public (GitHub Pages) and serves readers in different cities. Currently the newspaper weatherbar shows only the first line of a single city's agent-generated text.

## Goals

- Show full weather content in the newspaper weatherbar (not just one line)
- Support multiple cities so readers see weather for their location
- Auto-detect the reader's city; allow manual switching via dropdown
- Save token cost by batching popular-city LLM descriptions into one call
- Keep the email channel's personal weather untouched

## Non-Goals

- Server-side rendering (newspaper is static HTML on GitHub Pages)
- Cross-device sync of city preference
- Real-time weather updates (data is baked at generation time)

---

## Architecture

### 1. Config Changes

`WeatherConfig` in `src/app/config.py` gains a `cities` list:

```python
class CityWeatherConfig(BaseModel):
    name: str          # "北京"
    adcode: str        # "100085"
    popular: bool = False  # True = LLM-polished description

class WeatherConfig(BaseModel):
    enabled: bool = False
    api_url: str = "https://uapis.cn/api/v1/misc/weather"
    api_key: Optional[str] = None
    cities: list[CityWeatherConfig] = [...]  # 15+ defaults
    # Existing personal fields (for email channel):
    city: str = "北京"
    adcode: str = "100085"
    schedule: Optional[str] = None
```

Default `cities` list (15+ major cities, top 8 marked `popular: true`):

Popular: Beijing, Shanghai, Guangzhou, Shenzhen, Chengdu, Hangzhou, Wuhan, Chongqing.
Non-popular: Nanjing, Xi'an, Suzhou, Tianjin, Zhengzhou, Changsha, Dongguan, Qingdao, Kunming, Xiamen.

### 2. Pipeline (Build-Time)

File: `src/app/pipeline.py`, `src/app/weather.py`

1. **Fetch weather for all configured cities** — parallel HTTP calls to `uapis.cn`, one per city. Each returns raw factual text (conditions, temperature, wind, humidity, AQI, hourly forecasts).
2. **One LLM call for popular cities** — all `popular=True` cities' raw data sent in a single prompt. The LLM returns a short, friendly description per city (no personal schedule references). Output is a JSON dict keyed by city name.
3. **Non-popular cities** — raw weather text used as-is: replace `\n` with `<br>` for HTML, strip any schedule annotations in parentheses (e.g., "10:00（出门上班）" becomes "10:00").
4. **Personal email weather** — unchanged. Uses existing `city`/`adcode`/`schedule` fields, goes through the existing agent flow.
5. **Multi-city dict passed to newspaper renderer:**
   ```python
   {
       "北京": "晴朗宜出行，午后温暖但傍晚转凉，外出记得带薄外套。",
       "上海": "多云转阴，午后有短时阵雨，建议随身带伞。",
       "昆明": "晴，18°C，东南风2级，湿度52%，空气优\n...",
       ...
   }
   ```

### 3. Newspaper Renderer

File: `src/app/web/paper.py`

**HTML embedding** — all city weather data baked into a `<script>` JSON blob:

```html
<script>
var __weather = {
  "cities": ["北京","上海","广州","深圳",...],
  "data": {
    "北京": "晴朗宜出行，午后温暖...",
    "昆明": "晴，18°C，东南风2级...",
    ...
  },
  "default": "北京"
};
</script>
```

**Weatherbar HTML** — expanded with dropdown:

```html
<div class="weatherbar">
  <b>今日天气</b>
  <select class="city-select">
    <option value="北京">北京</option>
    <option value="上海">上海</option>
    ...
  </select>
  <div class="weather-text">晴朗宜出行...</div>
</div>
```

### 4. Client-Side Behavior

File: embedded `<script>` in generated HTML

**City resolution on page load (priority order):**

1. `localStorage.getItem('dispatch_city')` — saved manual preference
2. IP geolocation via `https://ip-api.com/json/` — silent, no permission popup
3. `__weather.default` — fallback (first city in config)

**IP geolocation flow:**
- Fire-and-forget fetch to `ip-api.com` — if it fails or is slow, default city shows immediately (no blocking)
- Match the returned city name against `__weather.cities`: strip "市" suffix, then check if any city name is a substring of the detected location (e.g., "朝阳区,北京" contains "北京")
- If no match, use default (first city in config list)

**Dropdown interaction:**
- On change: swap `weather-text` content from `__weather.data`, save to `localStorage`
- Defensive: if saved city not in today's data (config changed), fall back to IP detection then default

### 5. Styling

The `<select>` dropdown matches the newspaper aesthetic:
- `appearance: none` to strip browser chrome
- Serif font inherited from newspaper, `--muted` color
- Transparent background, thin bottom border (not a box)
- Subtle `▼` indicator via CSS pseudo-element
- On hover: accent color underline

Weather text: full multi-line, `<br>` separators, same font/color as existing weatherbar content.

---

## Files to Modify

| File | Change |
|------|--------|
| `src/app/config.py` | Add `CityWeatherConfig` model, extend `WeatherConfig` with `cities` list |
| `src/app/weather.py` | Add `fetch_weather_multi(cities)` for parallel multi-city fetch |
| `src/app/pipeline.py` | Call multi-city fetch, LLM batch call for popular cities, pass dict to newspaper |
| `src/app/digest/agent.py` | Add prompt/function for batch city weather descriptions (one LLM call) |
| `src/app/web/paper.py` | Accept multi-city weather dict, embed JSON, render dropdown weatherbar, add city-switch JS + IP geolocation JS, add dropdown CSS |
| `src/app/web/publish.py` | Thread multi-city weather dict through to `render_paper()` |

## Files Unchanged

| File | Reason |
|------|--------|
| `src/app/push/email.py` | Email keeps existing personal weather flow |
| `src/app/digest/render.py` | Email HTML rendering unchanged |
| `src/app/models.py` | Digest/Section model unchanged; multi-city data is passed separately to renderer, not stored in Section |

---

## Token Budget

Per daily run, for the multi-city LLM call only:

| Popular cities | Input tokens | Output tokens | Total |
|---------------|-------------|--------------|-------|
| 8 | ~1,600 | ~1,000 | ~2,600 |
| 10 | ~2,000 | ~1,200 | ~3,200 |
| 15 | ~2,900 | ~1,800 | ~4,700 |

Negligible relative to the existing digest generation (~10-20k tokens).

## Error Handling

- Weather API down for some cities: skip those cities, include only successful ones
- LLM call fails: fall back to raw text for all cities (graceful degradation)
- IP geolocation fails client-side: use default city immediately, no retry
- `localStorage` city not in today's data: fall back to IP detection then default
