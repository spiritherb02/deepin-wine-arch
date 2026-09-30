#!/usr/bin/env python3
"""从统信 UOS 应用商店源拉取移植所需的上游 .deb。

为什么不用 makepkg 的 source=()：商店源的下载必须带 `User-Agent: APT`，
而且真实资源全部 307 跳到 app-store-files.uniontech.com，PKGBUILD 里不方便表达。
所以由本脚本负责「按索引下载 + SHA256 校验」，PKGBUILD 只引用本地文件。

用法：
    python3 gen/fetch-debs.py                # 默认 crimson 通道
    python3 gen/fetch-debs.py eagle          # 换通道
"""
import gzip
import hashlib
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBS = os.path.join(ROOT, 'debs')

# 商店源。crimson 是当前的**最新**通道（beige 更旧，eagle 在 pro-store 主机且需要另一个 UA）。
CHANNELS = {
    'beige':   ('https://com-store-packages.uniontech.com/appstorev23', 'APT'),
    'crimson': ('https://com-store-packages.uniontech.com/appstorev23', 'APT'),
    'eagle':   ('https://pro-store-packages.uniontech.com/appstore', 'Debian APT-HTTP/1.3'),
}

# 需要移植的包（自造的 deepin-wine-builder-qt6compat / libyaml-cpp07 不在此列）
PKGS = [
    'deepin-wine11-stable',
    'deepin-wine10-stable',
    'deepin-wine8-stable',
    'deepin-wine-builder',
    'deepin-wine-helper',
    'deepin-wine-runtime',
    'deepin-wine-extras',
    'deepin-wine-logtool',
    'deepin-wine-diag',
]


def get(url, ua, timeout=120):
    req = urllib.request.Request(url, headers={'User-Agent': ua})
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_index(base, ua, channel):
    url = f'{base}/dists/{channel}/appstore/binary-amd64/Packages.gz'
    print(f'>>> 拉索引 {url}')
    with get(url, ua) as r:
        raw = r.read()
    print(f'    得到 {len(raw)} 字节')
    out = {}
    cur = {}
    for line in gzip.decompress(raw).decode('utf-8', 'replace').splitlines():
        if not line.strip():
            if cur.get('Package'):
                out[cur['Package']] = cur
            cur = {}
            continue
        if ': ' in line:
            k, v = line.split(': ', 1)
            cur[k] = v
    print(f'    索引共 {len(out)} 个包')
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    channel = sys.argv[1] if len(sys.argv) > 1 else 'crimson'
    if channel not in CHANNELS:
        sys.exit(f'未知通道 {channel}，可选：{", ".join(CHANNELS)}')
    base, ua = CHANNELS[channel]

    os.makedirs(DEBS, exist_ok=True)
    idx = fetch_index(base, ua, channel)

    ok = bad = 0
    for p in PKGS:
        meta = idx.get(p)
        if not meta:
            print(f'  ✘ {p}：索引里没有，跳过')
            bad += 1
            continue
        fname = meta['Filename']
        want = meta.get('SHA256')
        dest = os.path.join(DEBS, os.path.basename(fname))

        if os.path.exists(dest) and want and sha256(dest) == want:
            print(f'  = {os.path.basename(dest)}（已存在且校验通过，跳过）')
            ok += 1
            continue

        url = f'{base}/{fname.lstrip("/")}'
        print(f'  ↓ {os.path.basename(dest)}  ({int(meta.get("Size", 0)) / 1048576:.1f} MiB)')
        tmp = dest + '.part'
        try:
            with get(url, ua) as r, open(tmp, 'wb') as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:
            print(f'    ✘ 下载失败：{e}')
            os.path.exists(tmp) and os.remove(tmp)
            bad += 1
            continue

        got = sha256(tmp)
        if want and got != want:
            print(f'    ✘ SHA256 不匹配！期望 {want[:16]}… 实得 {got[:16]}…')
            os.remove(tmp)
            bad += 1
            continue
        os.replace(tmp, dest)
        print(f'    ✔ 校验通过  {os.path.basename(dest)}')
        ok += 1

    print(f'\n完成：成功 {ok} / 失败 {bad} → {DEBS}')
    if bad:
        sys.exit(1)


if __name__ == '__main__':
    main()
