#!/usr/bin/env python3
"""生成 deepin-wine 移植全套 PKGBUILD。

原则：
  * 每个 deb → 一个 Arch 包，deb 原样解包到 pkgdir（不 patch），保证与官方一致。
  * depends 由 deb 的 Depends 映射到 Arch 包名；Recommends → optdepends。
  * deb 里依赖 deepin-elf-verify 的，一律不映射（已确认无代码调用）。
"""
import os, shutil, hashlib, textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBS = os.path.join(ROOT, 'debs')
PKGS = os.path.join(ROOT, 'pkg')

# ---------- Debian → Arch 依赖映射 ----------
MAP = {
    'libasound2': 'alsa-lib', 'libc6': 'glibc', 'libdbus-1-3': 'dbus',
    'libgcc1': 'gcc-libs', 'libgcc-s1': 'gcc-libs', 'libstdlibc++6': 'gcc-libs',
    'libstdc++6': 'gcc-libs', 'libglib2.0-0': 'glib2',
    'libgphoto2-6': 'libgphoto2', 'libgphoto2-port12': 'libgphoto2',
    'libgstreamer-plugins-base1.0-0': 'gst-plugins-base-libs',
    'libgstreamer1.0-0': 'gstreamer', 'libpcap0.8': 'libpcap',
    'libpcsclite1': 'pcsclite', 'libpixman-1-0': 'pixman', 'libpng16-16': 'libpng',
    'libpulse0': 'libpulse', 'libsane': 'sane', 'libsane1': 'sane',
    'libudev1': 'systemd-libs', 'libunwind8': 'libunwind', 'libusb-1.0-0': 'libusb',
    'libwayland-client0': 'wayland', 'libwayland-egl1': 'wayland',
    'libx11-6': 'libx11', 'libxext6': 'libxext',
    'libxkbcommon0': 'libxkbcommon', 'libxkbregistry0': 'libxkbcommon',
    'ocl-icd-libopencl1': 'ocl-icd', 'zlib1g': 'zlib',
    'libasound2-plugins': 'alsa-plugins', 'libncurses6': 'ncurses',
    # builder
    'libarchive13': 'libarchive', 'libdtk6core': 'dtk6core', 'libdtk6gui': 'dtk6gui',
    'libdtk6log': 'dtk6log', 'libdtk6widget': 'dtk6widget',
    'libqt6concurrent6': 'qt6-base', 'libqt6core6': 'qt6-base', 'libqt6dbus6': 'qt6-base',
    'libqt6gui6': 'qt6-base', 'libqt6network6': 'qt6-base', 'libqt6sql6': 'qt6-base',
    'libqt6widgets6': 'qt6-base', 'libqt6xml6': 'qt6-base',
    'libqt6core5compat6': 'qt6-5compat', 'libqt6qml6': 'qt6-declarative',
    'libvulkan1': 'vulkan-icd-loader', 'libyaml-cpp0.7': 'libyaml-cpp07',
    'fakeroot': 'fakeroot', 'cabextract': 'cabextract', 'unrar': 'unrar',
    # helper
    'p7zip-full': '7zip', 'libgl1': 'libglvnd', 'fonts-noto-cjk': 'noto-fonts-cjk',
    'python3-dbus': 'python-dbus', 'x11-utils': 'xorg-xwininfo',
    # logtool
    'dconf-cli': 'dconf',
    'fonts-wqy-microhei': 'wqy-microhei',
    # 下面这些 Arch 没有，映射为空 → 丢弃
    'libcapi20-3': None, 'deepin-elf-verify': None, 'debhelper': None,
}

OPT_MAP = {
    'libcap2-bin': 'libcap', 'libcups2': 'cups', 'libnss-myhostname': 'systemd',
    'libfontconfig1': 'fontconfig', 'libfreetype6': 'freetype2',
    'libglu1-mesa': 'glu', 'libglu1': 'glu', 'libgnutls30': 'gnutls',
    'libgnutls28': 'gnutls', 'libgnutls26': 'gnutls',
    'libgssapi-krb5-2': 'krb5', 'libkrb5-3': 'krb5', 'libjpeg62-turbo': 'libjpeg-turbo',
    'libjpeg8': 'libjpeg-turbo', 'libodbc1': 'unixodbc', 'libosmesa6': 'mesa',
    'libsdl2-2.0-0': 'sdl2-compat', 'libv4l-0': 'v4l-utils',
    'libxcomposite1': 'libxcomposite', 'libxcursor1': 'libxcursor',
    'libxfixes3': 'libxfixes', 'libxi6': 'libxi', 'libxinerama1': 'libxinerama',
    'libxrandr2': 'libxrandr', 'libxrender1': 'libxrender', 'libxxf86vm1': 'libxxf86vm',
}

# ---------- 包定义 ----------
# name, deb文件名, pkgver, 本地包追加依赖, 本地包 optdepends, 额外字段
P = [
    dict(name='deepin-wine11-stable', ver='11.0deepin4+v25',
         desc='WINE Is Not An Emulator - run MS Windows programs (Deepin/UOS build, Wine 11 stable)'),
    dict(name='deepin-wine8-stable', ver='8.16deepin45',
         desc='WINE Is Not An Emulator - run MS Windows programs (Deepin/UOS build, Wine 8 stable)'),
    dict(name='deepin-wine10-stable', ver='10.14deepin11',
         desc='WINE Is Not An Emulator - run MS Windows programs (Deepin/UOS build, Wine 10 stable)'),
    dict(name='deepin-wine-builder', ver='4.0.2+v25', debver='4.0.2+v25-1', rel='2',
         desc='统信 Windows 应用兼容引擎 (Deepin/UOS Windows application compatibility engine)',
         provides=['deepin-wine-runner'], conflicts=['deepin-wine-runner'],
         extra_depends=['deepin-wine10-stable', 'deepin-wine-builder-qt6compat',
                        # 必须：提供 Qt6 chameleon 样式插件 (libchameleon.so)。
                        # 缺它时 QStyleFactory::create("chameleon") 返回 nullptr，
                        # 引擎会调 nullptr->proxy() 直接段错误。
                        'deepin-qt6integration'],
         extra_opt=['deepin-wine11-stable', 'deepin-wine-staging', 'deepin-wine-logtool',
                    'deepin-wine-extras', 'deepin-qt6platform-plugins',
                    'vulkan-radeon', 'vulkan-intel', 'vulkan-nouveau'],
         install='deepin-wine-builder.install',
         makedepends=['patchelf'],
         patch_needed=[('opt/apps/deepin-wine-builder/files/bin/deepin-wine-builder',
                        'libdeepin-wine-qt6compat.so')],
         patch_desktop=['usr/share/applications/deepin-wine-builder.desktop',
                        'opt/apps/deepin-wine-builder/entries/applications/deepin-wine-builder.desktop']),
    dict(name='deepin-wine-helper', ver='5.4.12+v25', debver='5.4.12+v25-1', rel='1',
         desc='Deepin Wine Helper (DTK6/Qt6 runtime helper)'),
    dict(name='deepin-wine-runtime', ver='0.2.5',
         desc='Deepin Wine runtime (bundled 32-bit i386 runtime, no multilib needed)'),
    dict(name='deepin-wine-extras', ver='1.0.2', arch='any',
         desc='Deepin Wine offline additions (DXVK / VKD3D-Proton / Wine-Gecko / Wine-Mono)'),
    dict(name='deepin-wine-logtool', ver='1.0.4',
         desc='Tools for analyzing Deepin Wine runtime logs'),
    dict(name='deepin-wine-diag', ver='3.3.1.013', debver='3.3.1.013-1', rel='1',
         desc='GUI diagnostics frontend for Deepin Wine',
         extra_depends=['deepin-wine8-stable', 'deepin-wine-runtime', 'deepin-wine-helper'],
         extra_opt=['deepin-wine6-stable']),
]

INSTALL_BUILDER = r'''post_install() {
  # 与 deb 的 postinst 等价：让引擎接管 Windows 可执行文件与 msp/dwb。
  # 注意 .exe 要同时注册三类：真 PE 内容嗅探得到 vnd.microsoft.portable-executable，
  # 扩展名加权得到 x-msdownload，DOS 老程序才是 x-ms-dos-executable。
  for m in application/x-ms-dos-executable x-scheme-handler/deepinwine \
           application/x-msi application/x-wine-extension-msp \
           application/x-msdos-batch text/x-msdos-batch application/dwb \
           application/vnd.microsoft.portable-executable \
           application/x-msdownload application/x-dosexec \
           application/x-ms-shortcut; do
    xdg-mime default deepin-wine-builder.desktop "$m" 2>/dev/null || true
  done
  update-desktop-database -q 2>/dev/null || true
  echo ">> 统信 Windows 应用兼容引擎已注册 .exe/.msi/.bat/.lnk 默认打开方式"
}

post_upgrade() { post_install; }

post_remove() {
  # 不把关联指回别的 handler（可能同样不存在），而是【移除】默认关联，
  # 让系统回退到"无默认程序"，由用户自己重新指定。
  # 包安装脚本以 root 运行、拿不到用户 HOME，所以这里只给指引。
  update-desktop-database -q 2>/dev/null || true
  echo ">> 已卸载引擎。若 .exe 仍显示旧关联，请手动清理："
  echo "   xdg-mime default '' <mime>   # 或编辑 ~/.config/mimeapps.list"
}
'''

# 引擎 desktop 需要补的 MIME 类型：上游列表漏了真 .exe 的两类
# （内容嗅探 → vnd.microsoft.portable-executable；扩展名加权 → x-msdownload），
# 缺了会导致「双击真 .exe 不进引擎」。
MIMES_EXTRA = ('x-scheme-handler/deepinwine;application/dwb;application/x-ms-dos-executable;'
               'application/x-msi;application/x-wine-extension-msp;text/x-msdos-batch;'
               'application/x-msdos-batch;application/vnd.microsoft.portable-executable;'
               'application/x-msdownload;application/x-dosexec;application/x-ms-shortcut;')

def split_deps(s):
    out = []
    for raw in s.split(','):
        raw = raw.strip()
        if not raw:
            continue
        # 去掉版本约束和 arch 限定
        base = raw.split('(')[0].split('|')[0].strip()
        base = base.split(':')[0] if base.startswith(('linux:', 'any:')) else base
        out.append(base)
    return out

def parse_control(text):
    d = {}
    for line in text.splitlines():
        if ':' in line and not line.startswith((' ', '\t')):
            k, v = line.split(':', 1)
            d[k.strip()] = v.strip()
    return d

def deb_control(path):
    """用 ar + tar 读 control，避免依赖 dpkg。"""
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as t:
        subprocess.run(['ar', 'x', path, 'control.tar.xz'], cwd=t, check=True)
        subprocess.run(['tar', '-xf', 'control.tar.xz', './control'], cwd=t, check=True)
        return open(os.path.join(t, './control'), encoding='utf-8', errors='replace').read()

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

os.makedirs(PKGS, exist_ok=True)
made = []

for spec in P:
    name, ver = spec['name'], spec['ver']
    dv = spec.get('debver', ver)
    if name == 'deepin-wine-extras':
        deb = f'{name}_{dv}_all.deb'
    else:
        deb = f'{name}_{dv}_amd64.deb'
    debpath = os.path.join(DEBS, deb)
    if not os.path.exists(debpath):
        print(f'!! 缺 deb: {deb}')
        continue
    ctl = parse_control(deb_control(debpath))

    depends, optdepends = [], []
    for d in split_deps(ctl.get('Depends', '')):
        a = MAP.get(d, d)           # 未收录的原样保留（下面过滤）
        if a and a not in depends:
            depends.append(a)
    for d in split_deps(ctl.get('Recommends', '')):
        a = OPT_MAP.get(d)
        if a and a not in optdepends and a not in depends:
            optdepends.append(a)
    # 去掉未映射到的 Debian 原生名（Arch 上不存在），以及本次不移植的包
    debian_only = {'libcapi20-3', 'deepin-elf-verify', 'debhelper', 'dpkg',
                   'deepin-wine6-stable'}
    depends = [x for x in depends if x not in debian_only and not x.startswith('libc6')]
    for x in spec.get('extra_depends', []):
        if x not in depends:
            depends.append(x)
    for x in spec.get('extra_opt', []):
        if x not in optdepends and x not in depends:
            optdepends.append(x)

    d = os.path.join(PKGS, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)

    # 放一个 deb 符号链接，保证 PKGBUILD 自包含可重跑。
    # 用【相对】链接，换机器/换目录也不会断（仓库里靠 .gitignore 排除）。
    lnk = os.path.join(d, deb)
    if os.path.islink(lnk):
        os.remove(lnk)
    if not os.path.lexists(lnk):
        os.symlink(os.path.relpath(debpath, d), lnk)

    lines = []
    lines.append(f"# Maintainer: spiritherb <h3189458857@163.com>")
    lines.append(f"# 由 {os.path.basename(__file__)} 自动生成 — 来源: uniontech com-store appstorev23/crimson")
    lines.append(f"pkgname={name}")
    lines.append(f"pkgver={ver}")
    lines.append(f"pkgrel={spec.get('rel','1')}")
    lines.append(f'pkgdesc="{spec["desc"]}"')
    lines.append(f"arch=('{spec.get('arch','x86_64')}')")
    if spec.get('makedepends'):
        lines.append("makedepends=(" + ' '.join(f"'{x}'" for x in spec['makedepends']) + ")")
    lines.append("url=\"https://www.deepin.org\"")
    lines.append("license=('proprietary')")
    if spec.get('provides'):
        lines.append("provides=(" + ' '.join(f"'{x}'" for x in spec['provides']) + ")")
    if spec.get('conflicts'):
        lines.append("conflicts=(" + ' '.join(f"'{x}'" for x in spec['conflicts']) + ")")
    if spec.get('provides') == ['deepin-wine-runner']:
        lines.append("replaces=('deepin-wine-runner')")
    lines.append("depends=(")
    for x in depends:
        lines.append(f"  {x}")
    lines.append(")")
    if optdepends:
        lines.append("optdepends=(")
        for x in optdepends:
            lines.append(f"  '{x}'")
        lines.append(")")
    if spec.get('install'):
        lines.append(f"install={spec['install']}")
    lines.append("options=('!strip')")
    lines.append("")
    lines.append("_deb=\"$srcdir/__DEB__\"".replace('__DEB__', deb))
    lines.append(f"sha256sums=('{sha256(debpath)}')")
    lines.append("noextract=('" + deb + "')")
    lines.append("source=('" + deb + "')")
    lines.append("")
    lines.append("package() {")
    lines.append('  cd "$srcdir"')
    lines.append(f'  # 解出 deb 全部成员，只把 data.tar.* 灌进 pkgdir')
    lines.append(f'  ar x "{deb}"')
    lines.append('  tar -xf data.tar.* -C "$pkgdir"')
    for rel, so in spec.get('patch_needed', []):
        lines.append("")
        lines.append("  # 补 Qt6 ABI 缺口：挂上兼容垫片，免得启动时 symbol lookup error")
        lines.append(f'  patchelf --add-needed "{so}" "$pkgdir/{rel}"')
    if spec.get('patch_desktop'):
        lines.append("")
        lines.append("  # 补上游 desktop 漏掉的 MIME 类型（否则双击真 .exe 不进引擎）")
        lines.append(f'  _mimes="{MIMES_EXTRA}"')
        lines.append('  for _f in '
                     + ' '.join(f'"$pkgdir/{r}"' for r in spec['patch_desktop']) + '; do')
        lines.append('    [ -f "$_f" ] && sed -i "s|^MimeType=.*|MimeType=${_mimes}|" "$_f"')
        lines.append("  done")
    lines.append("}")
    open(os.path.join(d, 'PKGBUILD'), 'w').write('\n'.join(lines) + '\n')

    if spec.get('install'):
        open(os.path.join(d, spec['install']), 'w').write(INSTALL_BUILDER)

    made.append((name, ver, len(depends), len(optdepends)))

print(f'{"包名":34} {"版本":20} depends optdepends')
print('-' * 76)
for n, v, a, b in made:
    print(f'{n:34} {v:20} {a:^7} {b:^10}')
print(f'\n共 {len(made)} 个 PKGBUILD → {PKGS}')
