"""
拟物（skeuomorphism）多版报纸网页渲染。

输入 Digest（结构化 sections：版面名 + 条目 title/link/summary，天气版面用 text），
输出自包含 HTML：头版（masthead + 天气栏 + 头条导语 + 次条 + 本期导读）+ 各版面内页
（标题/来源/摘要/阅读全文，多栏），纸张质感 + 轻量交互（鼠标光照、悬浮圈注、翻折纸角），
无第三方依赖，含打印样式，适合 GitHub Pages。
"""

from __future__ import annotations

import html
import json as _json
from datetime import datetime
from urllib.parse import urlparse

from app.models import Digest, Section

_WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def _esc(s: str | None) -> str:
    return html.escape(s or "", quote=True)


def _domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url).netloc
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _parse_dt(generated_at: str | None) -> datetime:
    if generated_at:
        try:
            return datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now()


def _date_line(dt: datetime) -> str:
    return f"{dt.year}年{dt.month}月{dt.day}日　{_WEEKDAY_CN[dt.weekday()]}"


def _is_weather(name: str) -> bool:
    return "天气" in name


def _is_headline(name: str) -> bool:
    return "头条" in name


def _is_epic(name: str) -> bool:
    return "Epic" in name or "epic" in name


def _byline(it) -> str:
    extra = it.extra if isinstance(it.extra, dict) else {}
    src = extra.get("source_name") or _domain(it.link)
    t = extra.get("time")
    bits = [b for b in (src, t) if b]
    return "　·　".join(_esc(str(b)) for b in bits)


# ---------------------------------------------------------------- CSS / JS

_CSS = """
:root{
  --paper:#f3ece0; --paper2:#efe7d8; --ink:#1c1a17; --muted:#5a5347;
  --rule:#2a2722; --accent:#7a1f1a; --link:#243b6b;
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{margin:0;padding:40px 16px 90px;min-height:100vh;
  background:#2f2a25;
  background-image:radial-gradient(circle at 30% 10%, #3a342d 0%, #221e1a 75%);
  font-family:"Songti SC","Noto Serif SC","Source Han Serif SC",STSong,SimSun,Georgia,"Times New Roman",serif;
  color:var(--ink);-webkit-font-smoothing:antialiased;perspective:3200px;perspective-origin:50% 30%;position:relative;}
.stage{max-width:1060px;margin:0 auto;position:relative;transform-style:preserve-3d;}
.physics-controls{position:fixed;right:16px;bottom:16px;z-index:40;display:flex;align-items:center;gap:10px;
  padding:8px 10px;border:1px solid rgba(231,218,188,.32);border-radius:999px;background:rgba(47,42,37,.78);
  color:#efe7d8;box-shadow:0 10px 24px rgba(0,0,0,.28);backdrop-filter:blur(6px);
  font:12px/1.2 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
.physics-controls button{border:1px solid rgba(239,231,216,.38);border-radius:999px;background:rgba(239,231,216,.12);
  color:#efe7d8;padding:4px 10px;cursor:pointer;font:inherit;}
.physics-controls button:hover{background:rgba(239,231,216,.20);}
.physics-controls button:disabled{opacity:.42;cursor:not-allowed;}
.physics-controls label{display:flex;align-items:center;gap:6px;white-space:nowrap;}
.settle-intensity{width:86px;accent-color:var(--accent);}
.settle-intensity-value{min-width:1.8em;text-align:right;color:#d9cfba;}

.sheet{position:relative;background:var(--paper);
  background-image:
    radial-gradient(circle at 18% 10%, rgba(255,255,255,.45), transparent 42%),
    radial-gradient(circle at 84% 92%, rgba(120,90,50,.10), transparent 46%),
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix type='saturate' values='0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/></svg>");
  padding:46px 52px 56px;border-radius:2px;margin:0 auto 46px;
  box-shadow:0 2px 0 #d9cfba, 0 30px 60px rgba(0,0,0,.55), inset 0 0 60px rgba(120,90,50,.10);
  transform:translate3d(0,0,0) rotateX(0deg) rotateY(0deg) rotateZ(0deg);
  transform-origin:center 58%;transform-style:preserve-3d;will-change:transform;}
body.motion-off .sheet{transform:none!important;}
@media (prefers-reduced-motion:no-preference){
  html.has-motion-js:not(.settle-ready) .sheet{transform:rotateX(4.8deg) rotateY(-2.3deg) rotateZ(-3.4deg) translateY(-37px);}
}
.sheet::before,.sheet::after{content:"";position:absolute;inset:0;background:var(--paper2);
  border-radius:2px;z-index:-1;box-shadow:0 18px 40px rgba(0,0,0,.4);}
.sheet::before{transform:translate(6px,8px) rotate(.4deg);}
.sheet::after{transform:translate(11px,15px) rotate(-.6deg);}

.peel{position:absolute;top:0;right:0;width:50px;height:50px;cursor:pointer;z-index:5;
  background:linear-gradient(225deg, var(--paper) 46%, #cdbfa3 50%, #7c6f57 60%, rgba(0,0,0,.25) 100%);
  box-shadow:-3px 3px 8px rgba(0,0,0,.25);clip-path:polygon(100% 0,0 0,100% 100%);
  transition:width .18s,height .18s,box-shadow .18s;}
.peel:hover{width:80px;height:80px;box-shadow:-6px 6px 14px rgba(0,0,0,.35);}
a.peel{text-decoration:none;color:inherit;display:block;}

/* 报头 */
.masthead{text-align:center;border-bottom:4px double var(--rule);padding-bottom:14px;}
.masthead .corners{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);
  font-family:system-ui,sans-serif;letter-spacing:1px;text-transform:uppercase;}
.title{font-size:clamp(40px,7vw,78px);line-height:1.02;margin:.06em 0 .04em;letter-spacing:.06em;
  font-weight:700;text-shadow:0 1px 0 rgba(255,255,255,.5);}
.subtitle{font-size:13px;color:var(--muted);font-family:system-ui,sans-serif;letter-spacing:.35em;text-transform:uppercase;}
.dateline{display:flex;justify-content:center;gap:18px;margin-top:10px;font-size:13px;color:var(--muted);
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:6px 0;font-family:system-ui,sans-serif;}

.weatherbar{margin:16px 0 4px;padding:10px 16px;border:1px solid #c9bfa0;border-left:4px solid var(--accent);
  background:rgba(255,255,255,.35);font-size:14px;line-height:1.65;}
.weatherbar b{font-family:system-ui,sans-serif;color:var(--accent);letter-spacing:.1em;}
.city-picker{position:relative;display:inline-block;margin-left:8px;font-family:system-ui,sans-serif;}
.city-current{cursor:pointer;border-bottom:1px solid var(--muted);padding:2px 16px 2px 4px;font-size:14px;color:var(--ink);
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='6'><path d='M0 0l5 6 5-6z' fill='%235a5347'/></svg>") no-repeat right 2px center/8px 5px;}
.city-current:hover{border-bottom-color:var(--accent);color:var(--accent);}
.city-list{display:none;position:absolute;top:100%;left:0;z-index:10;background:var(--paper);border:1px solid #c9bfa0;
  box-shadow:0 4px 12px rgba(0,0,0,.15);max-height:260px;overflow-y:auto;min-width:100px;}
.city-list.open{display:block;}
.city-list span{display:block;padding:5px 14px;cursor:pointer;font-size:13px;white-space:nowrap;}
.city-list span:hover{background:rgba(122,31,26,.08);color:var(--accent);}
.city-list span.active{font-weight:700;color:var(--accent);}
.weather-text{margin-top:8px;white-space:pre-line;}

/* 头版网格：头条 + 导读 */
.frontgrid{display:grid;grid-template-columns:1fr 270px;gap:34px;margin-top:18px;}
.lead-label{font-size:13px;letter-spacing:.4em;color:var(--accent);font-family:system-ui,sans-serif;
  text-transform:uppercase;margin-bottom:6px;}
.lead-main{display:block;text-decoration:none;color:var(--ink);padding:10px 12px 14px;margin:0 -12px 14px;
  border-bottom:2px solid var(--rule);position:relative;isolation:isolate;}
.lead-main .lt{font-size:clamp(28px,4.6vw,46px);line-height:1.14;font-weight:700;display:inline;transition:color .08s;}
.lead-main .standfirst{font-size:17px;line-height:1.7;color:#34302a;margin-top:10px;font-style:normal;}
.lead-main .by{font-size:12px;color:var(--muted);font-family:system-ui,sans-serif;margin-top:8px;}
.lead-rest .hl{display:block;text-decoration:none;color:var(--ink);padding:10px 12px;margin:0 -12px;border-top:1px dotted #b9ac90;
  position:relative;isolation:isolate;}
.lead-rest .hl .t{font-size:19px;line-height:1.3;font-weight:700;display:inline;transition:color .08s;}
.lead-rest .hl .s{display:block;font-size:13.5px;color:#4a443b;line-height:1.55;margin-top:3px;}
.lead-main::before,.lead-rest .hl::before{content:"📌";position:absolute;top:3px;right:4px;font-size:14px;line-height:1;opacity:0;
  transition:opacity .08s;pointer-events:none;z-index:3;}
.lead-main::after,.lead-rest .hl::after{content:"";position:absolute;top:6px;right:6px;bottom:7px;left:6px;
  border:2.2px dashed rgba(180,40,30,0);border-radius:50% 48% 52% 49% / 44% 48% 52% 56%;
  outline:1.4px dashed rgba(180,40,30,0);outline-offset:3px;
  transform:rotate(-7deg) scaleX(.98) scaleY(.94);transform-origin:center;opacity:0;transition:opacity .08s,border-color .08s,outline-color .08s;
  pointer-events:none;z-index:1;}
.lead-main:hover::before,.lead-rest .hl:hover::before{opacity:1;}
.lead-main:hover::after,.lead-rest .hl:hover::after{opacity:1;border-color:rgba(180,40,30,.30);
  outline-color:rgba(180,40,30,.13);}
.lead-main:hover .lt,.lead-rest .hl:hover .t{color:var(--accent);}

.index{border:1px solid var(--rule);background:rgba(255,255,255,.28);padding:14px 16px;height:max-content;}
.index h3{margin:0 0 10px;font-size:16px;border-bottom:1px solid var(--rule);padding-bottom:6px;letter-spacing:.1em;}
.index ul{list-style:none;margin:0;padding:0;}
.index li{margin:0 0 7px;}
.index a{display:flex;justify-content:space-between;gap:8px;text-decoration:none;color:var(--ink);font-size:14px;}
.index a:hover{color:var(--accent);}
.index a .pg{color:var(--muted);font-family:system-ui,sans-serif;white-space:nowrap;}

/* 内页 */
.pagehead{display:flex;align-items:baseline;justify-content:space-between;border-bottom:3px double var(--rule);
  padding-bottom:8px;margin-bottom:14px;}
.pagehead h2{margin:0;font-size:26px;letter-spacing:.06em;}
.pagehead .ed{font-size:12px;color:var(--muted);font-family:system-ui,sans-serif;letter-spacing:.1em;}
.columns{column-width:320px;column-gap:36px;column-rule:1px solid #cfc2a6;}
.art{break-inside:avoid;-webkit-column-break-inside:avoid;page-break-inside:avoid;display:block;text-decoration:none;
  color:var(--ink);padding:12px;margin:0 -12px 8px;border-bottom:1px solid #d7cab0;position:relative;isolation:isolate;}
.art::before{content:"📌";position:absolute;top:7px;right:9px;font-size:14px;line-height:1;opacity:0;
  transition:opacity .08s;pointer-events:none;z-index:3;}
.art::after{content:"";position:absolute;top:6px;right:6px;bottom:8px;left:6px;
  border:2.2px dashed rgba(180,40,30,0);border-radius:50% 48% 52% 49% / 44% 48% 52% 56%;
  outline:1.4px dashed rgba(180,40,30,0);outline-offset:3px;
  transform:rotate(-7deg) scaleX(.98) scaleY(.94);transform-origin:center;opacity:0;transition:opacity .08s,border-color .08s,outline-color .08s;
  pointer-events:none;z-index:1;}
.art:hover::before{opacity:1;}
.art:hover::after{opacity:1;border-color:rgba(180,40,30,.30);
  outline-color:rgba(180,40,30,.13);}
.art .at{font-size:18px;line-height:1.34;font-weight:700;display:inline;transition:color .08s;}
.art:hover .at{color:var(--accent);}
.art .by{font-size:11.5px;color:var(--muted);font-family:system-ui,sans-serif;margin:4px 0 6px;letter-spacing:.03em;}
.art .as{font-size:14px;line-height:1.66;color:#34302a;margin:0;text-align:justify;}
.art .more{display:inline-block;margin-top:6px;font-size:12px;color:var(--link);font-family:system-ui,sans-serif;}

/* Epic 卡片 */
.epic{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;}
.epic a{text-decoration:none;color:inherit;border:1px solid #cfc2a6;border-radius:8px;overflow:hidden;background:rgba(255,255,255,.45);}
.epic img{width:100%;height:150px;object-fit:cover;display:block;}
.epic .ec{padding:10px 12px;}
.epic .et{font-weight:700;font-size:15px;}
.epic .em{font-size:12px;color:var(--muted);font-family:system-ui,sans-serif;margin-top:5px;}

.colophon{margin-top:26px;padding-top:12px;border-top:4px double var(--rule);display:flex;justify-content:space-between;
  font-size:12px;color:var(--muted);font-family:system-ui,sans-serif;letter-spacing:.06em;}
.colophon a{color:var(--link);text-decoration:none;}
.colophon a:hover{text-decoration:underline;}

@media (max-width:760px){
  body{padding:18px 8px 50px;}
  .physics-controls{left:8px;right:8px;bottom:8px;justify-content:center;flex-wrap:wrap;border-radius:14px;}
  .sheet{padding:26px 20px 36px;}
  .frontgrid{grid-template-columns:1fr;}
  .columns{column-width:auto;column-count:1;}
}
@media (prefers-reduced-motion:reduce){
  .sheet{transform:none!important;}
}
@media print{
  body{background:#fff;padding:0;perspective:none;}
  .physics-controls{display:none;}
  .sheet{box-shadow:none;margin:0;page-break-after:always;}
  .sheet::before,.sheet::after,.peel{display:none;}
}
"""

_JS = """
(function(){
  var motionQuery=window.matchMedia&&window.matchMedia('(prefers-reduced-motion:reduce)');
  var reduceMotion=!!(motionQuery&&motionQuery.matches);
  var fine=window.matchMedia&&window.matchMedia('(pointer:fine)').matches;
  var root=document.documentElement;
  var sheets=Array.prototype.slice.call(document.querySelectorAll('.sheet'));
  sheets.forEach(function(sheet){
    var peel=sheet.querySelector('.peel');
    if(peel&&peel.tagName!=='A') peel.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
  });
  function clamp(n,min,max){return Math.max(min,Math.min(max,n));}
  function storeGet(k,d){try{var v=localStorage.getItem(k);return v===null?d:v;}catch(e){return d;}}
  function storeSet(k,v){try{localStorage.setItem(k,v);}catch(e){}}
  function S(k,c){return {x:0,v:0,t:0,k:k,c:c};}
  function stepSpring(s,dt){
    var f=-s.k*(s.x-s.t)-s.c*s.v;
    s.v+=f*dt;
    s.x+=s.v*dt;
  }
  var controllers=sheets.map(function(sheet,i){
    sheet.style.willChange='transform';
    sheet.style.transformStyle='preserve-3d';
    return {
      sheet:sheet,index:i,
      px:.5,py:.4,over:false,
      rx:S(90,12),
      ry:S(90,12),
      rz:S(80,11),
      ty:S(70,9)
    };
  });
  var intensity=clamp(parseFloat(storeGet('dispatch_settle_intensity_v2','1'))||0,0,2);
  var drapeIntensity=clamp(parseFloat(storeGet('dispatch_drape_intensity_v6','1'))||0,0,2);
  var manualOff=storeGet('dispatch_settle_motion_off_v2','0')==='1';
  var raf=0,lastFrame=0,lastImpulse=0,scrollPauseMs=900,lastScrollAt=performance.now();
  var replay=document.querySelector('.settle-replay');
  var intensityInput=document.querySelector('.settle-intensity');
  var intensityValue=document.querySelector('.settle-intensity-value');
  var motionToggle=document.querySelector('.settle-motion');
  function motionAllowed(){return !reduceMotion&&!manualOff;}
  function settleOn(){return motionAllowed()&&intensity>0;}
  function drapeOn(){return motionAllowed()&&fine&&drapeIntensity>0;}
  function render(c){
    c.sheet.style.transform='rotateX('+c.rx.x.toFixed(3)+'deg) rotateY('+c.ry.x.toFixed(3)+'deg) rotateZ('+c.rz.x.toFixed(3)+'deg) translateY('+c.ty.x.toFixed(2)+'px)';
  }
  function zeroAxis(a){a.x=a.t;a.v=0;}
  function flatten(c){
    c.rx.t=0;c.ry.t=0;c.rz.t=0;c.ty.t=0;
    zeroAxis(c.rx);zeroAxis(c.ry);zeroAxis(c.rz);zeroAxis(c.ty);
    c.sheet.style.transform='';
  }
  function rest(c){
    zeroAxis(c.rx);zeroAxis(c.ry);zeroAxis(c.rz);zeroAxis(c.ty);
    if(Math.abs(c.rx.x)>.001||Math.abs(c.ry.x)>.001||Math.abs(c.rz.x)>.001||Math.abs(c.ty.x)>.001)render(c);
    else c.sheet.style.transform='';
  }
  function flattenAll(){if(raf){cancelAnimationFrame(raf);raf=0;}lastFrame=0;controllers.forEach(flatten);}
  function scheduleSprings(){if(!raf){lastFrame=0;raf=requestAnimationFrame(stepSprings);}}
  function syncControls(){
    document.body.classList.toggle('motion-off',!motionAllowed());
    if(intensityInput) intensityInput.value=String(intensity);
    if(intensityValue) intensityValue.textContent=intensity.toFixed(1);
    if(motionToggle){
      motionToggle.checked=!manualOff&&!reduceMotion;
      motionToggle.disabled=reduceMotion;
      motionToggle.title=reduceMotion?'系统已开启减少动态效果':'';
    }
    if(replay) replay.disabled=!settleOn();
    if(!motionAllowed()){
      root.classList.add('settle-ready');
      flattenAll();
    }
  }
  function impulse(c,scale){
    if(!settleOn())return;
    var sign=c.index%2?-1:1;
    var I=intensity*(scale==null?1:scale);
    c.rx.x+=4.2*I*sign;c.rx.v+=-30*I*sign;
    c.ry.x+=-2.0*I*sign;c.ry.v+=14*I*sign;
    c.rz.x+=-3.0*I*sign;c.rz.v+=9*I*sign;
    c.ty.x=-32*I;c.ty.v=0;
    render(c);
  }
  function settleImpulse(targets,scale){
    if(!targets||!targets.length)return;
    root.classList.add('settle-ready');
    if(!settleOn()){if(!motionAllowed())targets.forEach(flatten);return;}
    lastImpulse=performance.now();
    targets.forEach(function(c){impulse(c,scale);});
    scheduleSprings();
  }
  function applyDrapeTarget(c){
    if(drapeOn()&&c.over){
      c.ry.t=clamp((c.px-.5)*3.4*drapeIntensity,-3.4,3.4);
      c.rx.t=clamp((c.py-.4)*-2.8*drapeIntensity,-2.8,2.8);
    }else{
      c.ry.t=0;c.rx.t=0;
    }
  }
  function axisMoving(a,epsX,epsV){
    if(Math.abs(a.x-a.t)<epsX&&Math.abs(a.v)<epsV){a.x=a.t;a.v=0;return false;}
    return true;
  }
  function integrate(c,dt){
    var moving=false,remaining=dt;
    while(remaining>0){
      var dtStep=Math.min(remaining,1/120);
      stepSpring(c.rx,dtStep);stepSpring(c.ry,dtStep);stepSpring(c.rz,dtStep);stepSpring(c.ty,dtStep);
      remaining-=dtStep;
    }
    moving=axisMoving(c.rx,.018,.04)||moving;
    moving=axisMoving(c.ry,.018,.04)||moving;
    moving=axisMoving(c.rz,.018,.04)||moving;
    moving=axisMoving(c.ty,.05,.08)||moving;
    return moving;
  }
  function stepSprings(now){
    raf=0;
    if(!motionAllowed()){flattenAll();return;}
    if(!lastFrame)lastFrame=now;
    var dt=Math.min((now-lastFrame)/1000,.032);
    lastFrame=now;
    controllers.forEach(function(c){
      applyDrapeTarget(c);
      integrate(c,dt);
      render(c);
    });
    raf=requestAnimationFrame(stepSprings);
  }
  function visibleControllers(){
    var h=window.innerHeight||document.documentElement.clientHeight||0;
    return controllers.filter(function(c){
      var r=c.sheet.getBoundingClientRect();
      return r.bottom>-120&&r.top<h+120;
    });
  }
  if(fine){
    window.addEventListener('mousemove',function(e){
      controllers.forEach(function(c){
        var r=c.sheet.getBoundingClientRect();
        c.px=(e.clientX-r.left)/r.width;
        c.py=(e.clientY-r.top)/r.height;
        c.over=c.px>=-.05&&c.px<=1.05&&c.py>=-.05&&c.py<=1.05;
      });
      if(motionAllowed())scheduleSprings();
    },{passive:true});
    document.addEventListener('mouseleave',function(){
      controllers.forEach(function(c){c.over=false;});
      if(motionAllowed())scheduleSprings();
    });
  }
  if(intensityInput){
    intensityInput.addEventListener('input',function(){
      intensity=clamp(parseFloat(intensityInput.value)||0,0,2);
      storeSet('dispatch_settle_intensity_v2',String(intensity));
      syncControls();
    });
  }
  if(motionToggle){
    motionToggle.addEventListener('change',function(){
      manualOff=!motionToggle.checked;
      storeSet('dispatch_settle_motion_off_v2',manualOff?'1':'0');
      syncControls();
      if(settleOn())settleImpulse(visibleControllers());
    });
  }
  if(replay)replay.addEventListener('click',function(){settleImpulse(controllers);});
  window.paperSettle=function(scale){settleImpulse(controllers,scale);};
  window.setPaperIntensity=function(v){
    intensity=clamp(parseFloat(v)||0,0,2);
    storeSet('dispatch_settle_intensity_v2',String(intensity));
    syncControls();
  };
  window.setDrapeIntensity=function(v){
    drapeIntensity=clamp(parseFloat(v)||0,0,2);
    storeSet('dispatch_drape_intensity_v6',String(drapeIntensity));
    if(motionAllowed())scheduleSprings();
  };
  if(motionQuery){
    var onReduceChange=function(e){reduceMotion=!!e.matches;syncControls();if(settleOn())settleImpulse(visibleControllers());};
    if(motionQuery.addEventListener)motionQuery.addEventListener('change',onReduceChange);
    else if(motionQuery.addListener)motionQuery.addListener(onReduceChange);
  }
  window.addEventListener('scroll',function(){
    var now=performance.now();
    if(now-lastScrollAt>scrollPauseMs&&now-lastImpulse>900)settleImpulse(visibleControllers(),.45);
    lastScrollAt=now;
  },{passive:true});
  syncControls();
  if(motionAllowed())scheduleSprings();
  setTimeout(function(){settleImpulse(controllers,1.15);},120);
  if(typeof __weather!=='undefined'&&__weather.data){
    var wd=__weather.data,wc=__weather.cities,wdef=__weather.default;
    var cur=document.querySelector('.city-current');
    var list=document.querySelector('.city-list');
    var txt=document.querySelector('.weather-text');
    if(cur&&list&&txt){
      function setCity(c){
        if(!wd[c])c=wdef;
        cur.textContent=c;
        txt.textContent=wd[c];
        var spans=list.querySelectorAll('span');
        for(var j=0;j<spans.length;j++) spans[j].className=spans[j].getAttribute('data-city')===c?'active':'';
        list.className='city-list';
      }
      cur.addEventListener('click',function(e){
        e.stopPropagation();
        list.className=list.className.indexOf('open')>=0?'city-list':'city-list open';
      });
      list.addEventListener('click',function(e){
        var t=e.target;if(t.tagName!=='SPAN')return;
        var c=t.getAttribute('data-city');if(!c)return;
        setCity(c);
        try{localStorage.setItem('dispatch_city',c);}catch(e){}
      });
      document.addEventListener('click',function(){list.className='city-list';});
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
})();
"""


# ---------------------------------------------------------------- pieces


def _render_city_weatherbar(city_weather: dict[str, str]) -> str:
    default_city = next(iter(city_weather))
    items = "".join(
        f'<span data-city="{_esc(c)}">{_esc(c)}</span>' for c in city_weather
    )
    return (
        f'<div class="weatherbar"><b>今日天气</b>'
        f'<div class="city-picker"><span class="city-current">{_esc(default_city)}</span>'
        f'<div class="city-list">{items}</div></div>'
        f'<div class="weather-text">{_esc(city_weather[default_city])}</div></div>'
    )


def _render_article(it, show_summary: bool) -> str:
    by = _byline(it)
    summ = f'<p class="as">{_esc(it.summary)}</p>' if (show_summary and it.summary) else ""
    return (
        f'<a class="art" href="{_esc(it.link)}" target="_blank" rel="noopener">'
        f'<span class="at">{_esc(it.title)}</span>'
        + (f'<div class="by">{by}</div>' if by else "")
        + summ
        + '<span class="more">阅读全文 →</span></a>'
    )


def _render_epic_page(sec: Section, idx: int, total: int, archive_href: str) -> str:
    cards = ""
    for it in sec.items:
        extra = it.extra if isinstance(it.extra, dict) else {}
        cover = extra.get("cover") or ""
        end = extra.get("free_end") or ""
        price = extra.get("original_price_desc") or ""
        badge = "🎁 免费领取中" if extra.get("is_free_now") else "⏳ 即将免费"
        cards += (
            f'<a href="{_esc(it.link)}" target="_blank" rel="noopener">'
            + (f'<img src="{_esc(cover)}" alt="">' if cover else "")
            + f'<div class="ec"><div class="et">{_esc(it.title)}</div>'
            f'<div class="em">{badge}　截止 {_esc(end)}　<s>{_esc(price)}</s> 免费</div></div></a>'
        )
    return _wrap_page(
        sec.name, idx, total,
        f'<div class="epic">{cards}</div>', archive_href,
    )


def _peel(prev_href: str | None) -> str:
    if prev_href:
        return f'<a class="peel" href="{_esc(prev_href)}" title="前一天报纸"></a>'
    return '<div class="peel" title="回到顶部"></div>'


def _wrap_page(name: str, idx: int, total: int, inner: str, archive_href: str) -> str:
    return (
        f'<div class="sheet" id="page-{idx}"><div class="peel" title="回到顶部"></div>'
        f'<div class="pagehead"><h2>{_esc(name)}</h2><span class="ed">第 {idx} 版 / 共 {total} 版</span></div>'
        f'{inner}'
        f'<div class="colophon"><a href="#page-1">← 返回头版</a><a href="{_esc(archive_href)}">往期 →</a></div></div>'
    )


def _render_front(
    *, title, masthead_en, issue, dt, weather: Section | None,
    headline: Section | None, index_entries, total, archive_href, show_summary,
    prev_href: str | None = None, city_weather: dict[str, str] | None = None,
) -> str:
    wbar = ""
    if city_weather:
        wbar = _render_city_weatherbar(city_weather)
    elif weather and weather.text:
        wbar = f'<div class="weatherbar"><b>{_esc(weather.name)}</b>　{_esc(weather.text).splitlines()[0] if weather.text else ""}</div>'

    lead = ""
    if headline and headline.items:
        first = headline.items[0]
        rest = headline.items[1:]
        standfirst = f'<p class="standfirst">{_esc(first.summary)}</p>' if (show_summary and first.summary) else ""
        by = _byline(first)
        lead = (
            '<div class="lead"><div class="lead-label">今日头条</div>'
            f'<a class="lead-main" href="{_esc(first.link)}" target="_blank" rel="noopener">'
            f'<span class="lt">{_esc(first.title)}</span>{standfirst}'
            + (f'<div class="by">{by}</div>' if by else "")
            + '</a><div class="lead-rest">'
        )
        for it in rest:
            teaser = f'<span class="s">{_esc(it.summary)}</span>' if (show_summary and it.summary) else ""
            lead += (
                f'<a class="hl" href="{_esc(it.link)}" target="_blank" rel="noopener">'
                f'<span class="t">{_esc(it.title)}</span>{teaser}</a>'
            )
        lead += "</div></div>"
    else:
        lead = '<div class="lead"><div class="lead-label">今日头条</div><p>今日暂无头条。</p></div>'

    idx_items = "".join(
        f'<li><a href="#page-{pg}"><span>{_esc(nm)}</span><span class="pg">第 {pg} 版</span></a></li>'
        for nm, pg in index_entries
    )
    index = f'<aside class="index"><h3>本期导读</h3><ul>{idx_items}</ul></aside>'

    return (
        f'<div class="sheet front" id="page-1">{_peel(prev_href)}'
        '<header class="masthead">'
        f'<div class="corners"><span>{_esc(issue)}</span><span>AI 编纂 · 仅供阅读</span></div>'
        f'<h1 class="title">{_esc(title)}</h1><div class="subtitle">{_esc(masthead_en)}</div>'
        f'<div class="dateline"><span>{_esc(_date_line(dt))}</span></div></header>'
        f'{wbar}<div class="frontgrid">{lead}{index}</div>'
        f'<div class="colophon"><span>第 1 版 · 头版</span><a href="{_esc(archive_href)}">查看往期 →</a></div></div>'
    )


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
    """将 Digest 渲染为拟物多版报纸 HTML。"""
    dt = _parse_dt(digest.generated_at)
    title = digest.title or "每日早报"
    issue = issue_label or f"第 {dt.strftime('%Y%m%d')} 期"

    weather = next((s for s in digest.sections if _is_weather(s.name) and s.text), None)
    headline = next((s for s in digest.sections if _is_headline(s.name) and s.items), None)
    inner = [
        s for s in digest.sections
        if s is not weather and s is not headline and (s.items or s.text)
    ]

    if not multi_page:
        # 单版：头条 + 全部版面塞进一张大报
        body = _render_single(title, masthead_en, issue, dt, weather, headline, inner, archive_href, show_summaries, prev_href, city_weather)
        return _document(title, masthead_en, body, city_weather=city_weather)

    # 多版：头版 + 每个版面一页
    total = 1 + len(inner)
    index_entries = [(s.name, 2 + i) for i, s in enumerate(inner)]
    pages = [
        _render_front(
            title=title, masthead_en=masthead_en, issue=issue, dt=dt, weather=weather,
            headline=headline, index_entries=index_entries, total=total,
            archive_href=archive_href, show_summary=show_summaries,
            prev_href=prev_href, city_weather=city_weather,
        )
    ]
    for i, sec in enumerate(inner):
        idx = 2 + i
        if _is_epic(sec.name):
            pages.append(_render_epic_page(sec, idx, total, archive_href))
        else:
            arts = "".join(_render_article(it, show_summaries) for it in sec.items)
            body = f'<div class="columns">{arts}</div>' if arts else (f'<p>{_esc(sec.text or "")}</p>')
            pages.append(_wrap_page(sec.name, idx, total, body, archive_href))
    return _document(title, masthead_en, "".join(pages), city_weather=city_weather)


def _render_single(title, masthead_en, issue, dt, weather, headline, inner, archive_href, show_summaries, prev_href=None, city_weather=None) -> str:
    wbar = ""
    if city_weather:
        wbar = _render_city_weatherbar(city_weather)
    elif weather and weather.text:
        wbar = f'<div class="weatherbar"><b>{_esc(weather.name)}</b>　{_esc(weather.text).splitlines()[0]}</div>'
    secs = ""
    ordered = ([headline] if headline else []) + inner
    for sec in ordered:
        if not sec:
            continue
        arts = "".join(_render_article(it, show_summaries) for it in sec.items)
        secs += f'<section><div class="pagehead"><h2>{_esc(sec.name)}</h2></div><div class="columns">{arts}</div></section>'
    return (
        f'<div class="sheet" id="page-1">{_peel(prev_href)}'
        '<header class="masthead">'
        f'<div class="corners"><span>{_esc(issue)}</span><span>AI 编纂</span></div>'
        f'<h1 class="title">{_esc(title)}</h1><div class="subtitle">{_esc(masthead_en)}</div>'
        f'<div class="dateline"><span>{_esc(_date_line(dt))}</span></div></header>'
        f'{wbar}{secs}'
        f'<div class="colophon"><span>{_esc(_date_line(dt))}</span><a href="{_esc(archive_href)}">往期 →</a></div></div>'
    )


def _document(title: str, masthead_en: str, body: str, *, city_weather: dict[str, str] | None = None) -> str:
    weather_script = ""
    if city_weather:
        cities_json = _json.dumps(city_weather, ensure_ascii=False)
        default_city = _esc(next(iter(city_weather)))
        weather_script = f'\n<script>var __weather={{data:{cities_json},cities:{_json.dumps(list(city_weather.keys()), ensure_ascii=False)},default:"{default_city}"}}</script>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN" class="has-motion-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
<noscript><style>.sheet{{transform:none!important;}}.physics-controls{{display:none!important;}}</style></noscript>
</head>
<body>
<div class="physics-controls" aria-label="报纸落下动效控制">
  <button type="button" class="settle-replay">重落 / Replay</button>
  <label>力度 <input class="settle-intensity" type="range" min="0" max="2" step="0.1" value="1"><span class="settle-intensity-value">1.0</span></label>
  <label><input class="settle-motion" type="checkbox" checked> 动效</label>
</div>
<div class="stage">
{body}
</div>{weather_script}
<script>{_JS}</script>
</body>
</html>
"""


def render_archive(entries: list[tuple[str, str]], *, masthead_en: str = "ARCHIVE") -> str:
    """生成往期索引页。entries: [(date_str, href), ...]，新到旧。"""
    items = "".join(
        f'<a class="art" href="{_esc(href)}"><span class="at">{_esc(d)} 早报</span>'
        f'<span class="by">{_esc(href)}</span></a>'
        for d, href in entries
    )
    if not items:
        items = "<p>暂无往期</p>"
    body = (
        '<div class="sheet"><div class="peel"></div>'
        '<header class="masthead"><h1 class="title">往期早报</h1>'
        f'<div class="subtitle">{_esc(masthead_en)}</div></header>'
        f'<div class="columns" style="margin-top:18px;">{items}</div>'
        '<div class="colophon"><a href="index.html">← 返回今日</a><span></span></div></div>'
    )
    return _document("早报 · 往期索引", masthead_en, body)


__all__ = ["render_paper", "render_archive"]
