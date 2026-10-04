# -*- coding: utf-8 -*-
"""下载《海绵城市建设技术指南（2014）》并提取附录3（单价估算表）文本。
输出: 04-数据/公开资料/海绵城市建设技术指南2014.pdf
      04-数据/公开资料/指南_附录3_单价估算_提取.txt
"""
import os
import ssl
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(ROOT, '..', '公开资料'))
os.makedirs(OUT, exist_ok=True)
PDF = os.path.join(OUT, '海绵城市建设技术指南2014.pdf')

if not os.path.exists(PDF):
    import urllib.request
    _SSL = ssl.create_default_context()
    _SSL.check_hostname = False
    _SSL.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        'https://img6.ccement.com/2015/07/20/a9ebe6eb.pdf',
        headers={'User-Agent': 'Mozilla/5.0'})
    data = urllib.request.urlopen(req, timeout=90, context=_SSL).read()
    with open(PDF, 'wb') as f:
        f.write(data)
    print('downloaded', len(data), 'bytes')

try:
    import pypdf
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'pypdf',
                           '--trusted-host', 'pypi.org',
                           '--trusted-host', 'files.pythonhosted.org'])
    import pypdf

reader = pypdf.PdfReader(PDF)
n = len(reader.pages)
print('pages', n)

chunks = []
for i in range(max(0, n - 30), n):      # 附录在文档末尾
    t = reader.pages[i].extract_text() or ''
    if '单价' in t or 'F3' in t or '估算' in t:
        chunks.append(f'--- page {i + 1} ---\n' + t)

text = '\n'.join(chunks)
path = os.path.join(OUT, '指南_附录3_单价估算_提取.txt')
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('saved', path, '| chars', len(text))
print(text[:3500])
