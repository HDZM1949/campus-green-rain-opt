# -*- coding: utf-8 -*-
"""底图下载 v3：支持 amap / esri / bing 三种瓦片源（尝试获取更新影像）

用法：
  python get_base_map3.py LAT LON Z N NAME [SRC] [STYLE]
    SRC: amap(默认) | esri | bing
    STYLE: amap 样式（6 卫星 / 7 矢量 / 8 注记），默认 6
说明：本机存在 SSL 证书拦截，下载公开影像时不校验证书。
输出：04-数据/场地/<NAME>.png 与 bounds_<NAME>.json
"""
import io, json, math, os, ssl, sys, time

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(ROOT, '..', '场地'))
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (compatible; campus-gi/0.3; student research)'}
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return r.read()


def deg2num(lat, lon, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lr = math.radians(lat)
    y = (1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * n
    return x, y


def num2deg(x, y, z):
    n = 2 ** z
    return (math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))),
            x / n * 360.0 - 180.0)


def tile2quad(x, y, z):
    q = []
    for i in range(z, 0, -1):
        d = 0
        if x & (1 << (i - 1)):
            d += 1
        if y & (1 << (i - 1)):
            d += 2
        q.append(str(d))
    return ''.join(q)


def make_url(src, z, x, y, style):
    if src == 'amap':
        return f'https://webst01.is.autonavi.com/appmaptile?style={style}&x={x}&y={y}&z={z}'
    if src == 'esri':
        return ('https://server.arcgisonline.com/ArcGIS/rest/services/'
                f'World_Imagery/MapServer/tile/{z}/{y}/{x}')
    if src == 'bing':
        return ('https://ecn.t3.tiles.virtualearth.net/tiles/'
                f'a{tile2quad(x, y, z)}.jpeg?g=13129&mkt=zh-CN')
    raise ValueError('unknown src: ' + src)


lat = float(sys.argv[1]); lon = float(sys.argv[2])
z = int(sys.argv[3]); n = int(sys.argv[4]); name = sys.argv[5]
src = sys.argv[6] if len(sys.argv) >= 7 else 'amap'
style = sys.argv[7] if len(sys.argv) >= 8 else '6'

xc, yc = deg2num(lat, lon, z)
x0, y0 = int(xc) - n // 2, int(yc) - n // 2

try:
    fetch(make_url(src, z, x0, y0, style), timeout=10)
    print('preflight ok:', src)
except Exception as e:
    raise SystemExit(f'preflight failed: {src} {e!r}')

img = Image.new('RGB', (n * 256, n * 256), (235, 235, 235))
ok = 0
for dx in range(n):
    for dy in range(n):
        url = make_url(src, z, x0 + dx, y0 + dy, style)
        try:
            img.paste(Image.open(io.BytesIO(fetch(url))).convert('RGB'),
                      (dx * 256, dy * 256))
            ok += 1
        except Exception as e:
            print('tile fail', z, x0 + dx, y0 + dy, repr(e)[:70])
        time.sleep(0.02)

img.save(os.path.join(OUT, f'{name}.png'))
lat_top, lon_left = num2deg(x0, y0, z)
lat_bot, lon_right = num2deg(x0 + n, y0 + n, z)
info = {'center': {'lat': lat, 'lon': lon}, 'source': src, 'style': style,
        'z': z, 'x0': x0, 'y0': y0, 'n': n,
        'lat_top': lat_top, 'lon_left': lon_left,
        'lat_bottom': lat_bot, 'lon_right': lon_right,
        'm_per_px_approx': 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)}
with open(os.path.join(OUT, f'bounds_{name}.json'), 'w', encoding='utf-8') as f:
    json.dump(info, f, ensure_ascii=False, indent=2)
print('SAVED', name, '| src', src, '| tiles ok', ok, '/', n * n)
