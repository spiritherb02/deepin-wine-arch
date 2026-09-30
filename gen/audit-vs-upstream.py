#!/usr/bin/env python3
"""审计：本地移植版 vs 统信上游（crimson 通道）

做两件事：
  1. 版本对齐：把上游 Packages 索引里的版本 vs 本地 PKGBUILD 的 pkgver 对照。
  2. 内容对齐：逐个 deb 解出 data.tar.* 的成员清单，与**磁盘上实际安装的文件**
     逐文件比 sha256（符号链接比目标）。只报差异，不报相同的。
"""
import gzip, hashlib, io, os, re, subprocess, sys, tarfile, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBS = os.path.join(ROOT, 'debs')
IDX = os.path.join(ROOT, 'audit', 'Packages.gz')

# 期望与 deb 一一对应的包（自制的两个不在列）
PKGS = ['deepin-wine11-stable', 'deepin-wine10-stable', 'deepin-wine8-stable',
        'deepin-wine-builder', 'deepin-wine-helper', 'deepin-wine-runtime',
        'deepin-wine-extras', 'deepin-wine-logtool', 'deepin-wine-diag']

# 已知的、有意的改动（会被报为 DIFF，属预期）
INTENTIONAL = {
    'opt/apps/deepin-wine-builder/files/bin/deepin-wine-builder':
        'patchelf --add-needed libdeepin-wine-qt6compat.so（补 Qt6 ABI 缺口）',
    'usr/share/applications/deepin-wine-builder.desktop':
        'MimeType 补齐真 .exe 的类型（vnd.microsoft.portable-executable / x-msdownload）',
    'opt/apps/deepin-wine-builder/entries/applications/deepin-wine-builder.desktop':
        '同上（entries 下的副本）',
}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def fetch_index():
    os.makedirs(os.path.dirname(IDX), exist_ok=True)
    if os.path.exists(IDX) and os.path.getsize(IDX) > 100000:
        return
    url = ('https://com-store-packages.uniontech.com/appstorev23/dists/crimson/'
           'appstore/binary-amd64/Packages.gz')
    req = urllib.request.Request(url, headers={'User-Agent': 'APT'})
    with urllib.request.urlopen(req, timeout=90) as r, open(IDX, 'wb') as f:
        f.write(r.read())


def index_versions():
    out = {}
    with gzip.open(IDX, 'rt', encoding='utf-8', errors='replace') as f:
        cur = {}
        for line in f:
            line = line.rstrip('\n')
            if not line:
                if cur.get('Package'):
                    out[cur['Package']] = cur
                cur = {}
                continue
            if ': ' in line:
                k, v = line.split(': ', 1)
                cur[k] = v
    return out


def debver_from_name(name):
    m = re.search(r'_([^_]+)_(?:amd64|all)\.deb$', name)
    return m.group(1) if m else None


def main():
    fetch_index()
    idx = index_versions()

    print('=' * 96)
    print('1) 版本对齐（上游 crimson 索引 vs 本地移植）')
    print('=' * 96)
    print(f"{'包名':30} {'上游索引版本':28} {'本地 deb 版本':22} 判定")
    print('-' * 96)
    allver_ok = True
    for p in PKGS:
        up = idx.get(p, {}).get('Version', '(索引里没有)')
        local_deb = next((f for f in os.listdir(DEBS) if f.startswith(p + '_')), None)
        lv = debver_from_name(local_deb) if local_deb else '(缺 deb)'
        ok = (up == lv)
        allver_ok &= ok
        print(f'{p:30} {up:28} {str(lv):22} {"一致 ✔" if ok else "不一致 ✘"}')
    print(f'\n版本结论：{"全部与上游一致" if allver_ok else "存在不一致"}')

    print()
    print('=' * 96)
    print('2) 内容对齐（deb 内文件 vs 磁盘上已安装的文件，逐文件 sha256）')
    print('=' * 96)
    total_same = total_diff = total_missing = 0
    diffs = []
    for p in PKGS:
        deb = next((f for f in os.listdir(DEBS) if f.startswith(p + '_')), None)
        if not deb:
            continue
        path = os.path.join(DEBS, deb)
        same = diff = missing = 0
        members = []
        # ar 解出 data.tar.*
        import tempfile
        os.makedirs(os.path.join(ROOT, '.work'), exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, '.work')) as t:
            subprocess.run(['ar', 'x', path], cwd=t, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            data = [f for f in os.listdir(t) if f.startswith('data.tar')][0]
            with tarfile.open(os.path.join(t, data)) as tf:
                for m in tf.getmembers():
                    rel = m.name.lstrip('./')
                    if not rel or m.isdir():
                        continue
                    members.append(m)
                    disk = '/' + rel
                    if m.issym():
                        if not os.path.islink(disk):
                            missing += 1
                            diffs.append((p, rel, '缺失(符号链接)'))
                        elif os.readlink(disk) == m.linkname:
                            same += 1
                        else:
                            diff += 1
                            diffs.append((p, rel, f'符号链接目标不同: 盘上={os.readlink(disk)} deb={m.linkname}'))
                        continue
                    if not m.isfile():
                        continue
                    if not os.path.exists(disk):
                        missing += 1
                        diffs.append((p, rel, '缺失'))
                        continue
                    src = tf.extractfile(m)
                    h1 = hashlib.sha256(src.read()).hexdigest()
                    h2 = sha(disk)
                    if h1 == h2:
                        same += 1
                    else:
                        diff += 1
                        diffs.append((p, rel, '内容不同'))
        total_same += same
        total_diff += diff
        total_missing += missing
        flag = '完全一致 ✔' if (diff == 0 and missing == 0) else f'有差异（改{diff} 缺{missing}）'
        print(f'{p:30} 相同 {same:7}  不同 {diff:4}  缺失 {missing:4}   {flag}')

    print()
    print('-' * 96)
    print(f'合计：相同 {total_same}  不同 {total_diff}  缺失 {total_missing}')
    print()
    if diffs:
        print('差异明细：')
        for p, rel, why in diffs:
            mark = '★预期改动' if rel in INTENTIONAL else '❗非预期'
            print(f'  [{mark}] {p}: {rel}  —  {why}')
            if rel in INTENTIONAL:
                print(f'              理由: {INTENTIONAL[rel]}')
    else:
        print('差异明细：无')


if __name__ == '__main__':
    main()
