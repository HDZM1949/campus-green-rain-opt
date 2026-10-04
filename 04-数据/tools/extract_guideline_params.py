# -*- coding: utf-8 -*-
"""从《海绵城市建设技术指南（2014）》本地 PDF 提取参数相关页；并测试本机外网源连通性。

输出：04-数据/公开资料/指南_参数相关页_提取.txt
"""
import os
import ssl
import sys
import urllib.request

import pypdf

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.abspath(os.path.join(ROOT, '..', '公开资料'))
PDF = os.path.join(PUB, '海绵城市建设技术指南2014.pdf')

reader = pypdf.PdfReader(PDF)
n = len(reader.pages)
print('pages:', n)

keys = ['径流系数', '下垫面', '渗透', '设计降雨', '控制率', '曲线数', 'CN值', 'LID']
hits = {}
for i in range(n):
    t = reader.pages[i].extract_text() or ''
    for k in keys:
        if k in t:
            hits.setdefault(i, set()).add(k)

print('hit pages:', {i + 1: sorted(v) for i, v in sorted(hits.items())})

out = []
for i in sorted(hits):
    out.append(f'===== page {i + 1} ({",".join(sorted(hits[i]))}) =====')
    out.append(reader.pages[i].extract_text() or '')
path = os.path.join(PUB, '指南_参数相关页_提取.txt')
with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('saved', path, '| pages', len(hits))

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


def head(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        r = urllib.request.urlopen(req, timeout=15, context=_SSL)
        return f'OK {r.status}, bytes={len(r.read(2000))}'
    except Exception as e:
        return f'FAIL {type(e).__name__}: {str(e)[:90]}'


tests = [
    ('baike_cn', 'https://baike.baidu.com/item/%E5%BE%84%E6%B5%81%E6%9B%B2%E7%BA%BF%E6%95%B0'),
    ('bing', 'https://cn.bing.com/search?q=%E6%B5%B7%E7%BB%B5%E5%9F%8E%E5%B8%82+CN%E5%80%BC'),
    ('so', 'https://www.so.com/s?q=%E6%B5%B7%E7%BB%B5%E5%9F%8E%E5%B8%82+CN'),
    ('zhiwang', 'https://www.cnki.net/'),
]
for name, u in tests:
    print(name, '->', head(u))
