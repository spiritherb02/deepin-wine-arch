# deepin-wine-arch

把 **统信 Windows 应用兼容引擎**（`deepin-wine-builder`）及其 deepin-wine 全家桶，
从统信 UOS 应用商店源移植到 **Arch Linux** 的打包脚本集。

装上之后，`.exe` / `.msi` 双击即可安装或运行 Windows 程序，与在 deepin/UOS 上体验一致。

> **非官方项目。** 与统信软件技术有限公司无隶属关系。详见 [NOTICE.md](NOTICE.md)。

---

## 这东西解决什么问题

统信商店里的包是 **Debian 格式**，而且商店源有下载门槛（必须带特定 `User-Agent`、
真实文件 307 跳转）。Arch 用户拿不到、也装不上。

更麻烦的是：**就算把 deb 硬解包铺到 `/` 上，它也跑不起来** —— 因为它是按 deepin 的
工具链和旧版 Qt 编译的，在滚动更新的 Arch 上会撞上两类 ABI 问题（见下）。

本项目的价值不在于「把文件拷过去」（那很简单），而在于**把这两类 ABI 缺口补齐**，
并给出可复现、可审计、可回滚的打包流程。

---

## 验证状态

在 Arch 系发行版 **pearOS + KDE Plasma 6 / Wayland / Qt 6.11** 上实测通过：

| 项目 | 结果 |
|---|---|
| 引擎启动（offscreen 与 xvfb 两种后端各 30s） | 稳定，无崩溃 |
| D-Bus 服务 `com.deepin.DeepinWineBuilder` | 已注册 |
| wine 11 端到端（`cmd /c echo`） | 通过 |
| 32 位支持（`Program Files (x86)` 存在） | 正常，**无需 multilib** |
| 与已安装包的**真实文件冲突** | **0** 条 |
| 引擎二进制 `ldd` 缺失依赖 | **0** |
| 与上游 deb 逐文件比对 | 10378 个文件，**差异仅 3 处且均为有意**（见下） |

---

## 快速开始

### 依赖

```bash
# 官方仓库
sudo pacman -S base-devel patchelf
# AUR（dtk6 系列与 Qt6 集成插件，缺一不可）
yay -S dtk6core dtk6gui dtk6widget dtk6log deepin-qt6integration
```

> `deepin-qt6integration` **不是可选的**，见下文「坑 2」。

### 三步构建

```bash
git clone https://github.com/spiritherb02/deepin-wine-arch.git
cd deepin-wine-arch

# 1) 从统信商店源拉上游 deb（自动按索引校验 SHA256），约 600 MiB
python3 gen/fetch-debs.py            # 默认 crimson 通道

# 2) 生成 PKGBUILD（会按 deb 的 Depends 映射出 Arch 依赖）
python3 gen/gen-pkgbuilds.py

# 3) 按依赖序构建全部 11 个包，产物落在 repo/
bash gen/build-all.sh
```

已提交的 PKGBUILD 可直接用（含校验和），第 2 步只在你想改依赖映射时才需要重跑。

### 安装

```bash
sudo pacman -U repo/*.pkg.tar.zst
```

装完它会自己把 `.exe` / `.msi` / `.bat` / `.lnk` 的默认打开方式注册到引擎。
启动台里会出现 **「统信Windows应用兼容引擎」**。

### 关于通道

商店源有三个通道，**`crimson` 才是最新线**（默认已选）：

| 通道 | 主机 | 包数 | 备注 |
|---|---|---|---|
| `beige` | `com-store-packages.uniontech.com/appstorev23` | 4421 | 较旧 |
| **`crimson`** | `com-store-packages.uniontech.com/appstorev23` | 3586 | **最新，默认** |
| `eagle` | `pro-store-packages.uniontech.com/appstore` | 65847 | 需另一套 UA |

> 只看 `beige` 会得出「wine8 就是最新」的错误结论。本项目最初就踩过这个坑。

---

## 装了哪些包

| 包 | 版本（crimson） | 说明 |
|---|---|---|
| `deepin-wine-builder` | 4.0.2+v25 | **引擎本体**（DTK6/Qt6 GUI） |
| `deepin-wine11-stable` | 11.0deepin4+v25 | Wine 11 |
| `deepin-wine10-stable` | 10.14deepin11 | Wine 10 |
| `deepin-wine8-stable` | 8.16deepin45 | Wine 8（兼容老软件） |
| `deepin-wine-helper` | 5.4.12+v25 | 运行时助手 |
| `deepin-wine-runtime` | 0.2.5 | **自带 32 位 i386 运行时，无需 multilib** |
| `deepin-wine-extras` | 1.0.2 | 离线 DXVK / VKD3D-Proton / Wine-Gecko / Wine-Mono |
| `deepin-wine-logtool` | 1.0.4 | 日志分析 |
| `deepin-wine-diag` | 3.3.1.013 | 诊断工具 |

另外两个是本项目**自己写的**，上游没有对应 deb：

| 包 | 说明 |
|---|---|
| `deepin-wine-builder-qt6compat` | Qt6 ABI 转发垫片（补「坑 1」） |
| `libyaml-cpp07` | 从 Arch 官方 archive 取 `yaml-cpp 0.7.0` 的 `.so`，与系统 0.9 并存 |

---

## 移植时踩的两个坑（本项目的核心内容）

### 坑 1：Qt 6.9 删掉了 `QListView` 的两个受保护虚函数 → 启动即 `symbol lookup error`

引擎的 deb 是按 **Qt 6.8** 编译的，动态符号表里引用了
`QListView::mousePressEvent` 和 `QListView::eventFilter`——这两个是 `protected` 的
override，**Qt 6.9 把它们删除了**。Arch 早已是 Qt 6.11，于是：

```
symbol lookup error: .../deepin-wine-builder:
  undefined symbol: _ZN9QListView11eventFilterEP7QObjectP6QEvent, version Qt_6
```

**做法**：写一个转发垫片，用 `asm()` 把函数名**抢注**成 Qt6 那套 mangled 符号，
实现体里通过 `QAbstractItemView` 基类指针调回那个 protected 函数：

```cpp
namespace { struct Access : QAbstractItemView {
    void callMousePress(QMouseEvent *e) { mousePressEvent(e); }
    bool callEventFilter(QObject *o, QEvent *e) { return eventFilter(o, e); }
}; }

extern "C" void qlistview_mousePressEvent(QListView *self, QMouseEvent *event)
    asm("_ZN9QListView15mousePressEventEP11QMouseEvent");   // ← 抢注 Qt 的符号名
extern "C" void qlistview_mousePressEvent(QListView *self, QMouseEvent *event) {
    auto *acc = reinterpret_cast<Access *>(static_cast<QAbstractItemView *>(self));
    acc->callMousePress(event);
}
```

配合版本脚本把符号挂到 `Qt_6` 命名空间下，最后**不改引擎本体**，只在打包时给它加一条
`NEEDED`：

```bash
patchelf --add-needed libdeepin-wine-qt6compat.so \
  "$pkgdir/opt/apps/deepin-wine-builder/files/bin/deepin-wine-builder"
```

完整源码见 `pkg/deepin-wine-builder-qt6compat/`（不到 40 行）。

### 坑 2：缺 chameleon 样式插件 → `QStyle::proxy()` 空指针段错误

引擎能起、界面能画，但**一交互就 SIGSEGV**，gdb 里 `rdi=0x0`（null this）。根因：

```cpp
QStyleFactory::create("chameleon")   // → nullptr（插件不在）
// 之后代码直接 nullptr->proxy()
```

`chameleon` 是 deepin 的 Qt 样式插件，**不在 `qt6-base` 里**，由 **`deepin-qt6integration`**
提供（`/usr/lib/qt6/plugins/styles/libchameleon.so`）。所以它是**硬依赖，不是美化选项**。

> 排查弯路提示：一开始怀疑是样式选错了，试过 `QT_STYLE_OVERRIDE=fusion`，**照样崩**。
> 判据是「缺哪个 QStyle 插件」而不是「样式好不好看」。

### 附带一个容易漏的：`.exe` 的 MIME 归属

真 Windows PE 文件经**内容嗅探**得到的是 `application/vnd.microsoft.portable-executable`，
按**扩展名加权**得到的是 `application/x-msdownload`。而上游 desktop 的 `MimeType` 里
**这两个都没写**（只写了 DOS 档的 `x-ms-dos-executable`）→ 装完引擎，双击真 `.exe` 依然
不会进引擎。

本项目在打包时用 `sed` 补齐 MimeType，并在 `.install` 里把 11 个相关类型都设一遍。

---

## 与上游的一致性（可自行复核）

```bash
python3 gen/audit-vs-upstream.py
```

脚本会拉上游索引比对版本，并把每个 deb 的内容与**磁盘上已安装的文件**逐文件比 SHA256。
实测结果：

**版本：9/9 与上游 `crimson` 索引完全一致。**

**内容：10378 个文件 → 相同 10378、缺失 0、不同 3。** 三处差异全部是有意的：

| 差异文件 | 具体改动 |
|---|---|
| `opt/apps/deepin-wine-builder/files/bin/deepin-wine-builder` | 动态依赖表**开头多一行** `libdeepin-wine-qt6compat.so`，其余 20 条 NEEDED 未动 |
| `usr/share/applications/deepin-wine-builder.desktop` | **只有 `MimeType` 那一行**被补齐 |
| `opt/apps/deepin-wine-builder/entries/.../deepin-wine-builder.desktop` | 同上（副本） |

**除这三处，所有二进制与资源文件都是 deb 原样解包，与上游逐字节相同。**

### 有意省略的上游依赖

| 上游依赖 | 处理 |
|---|---|
| `deepin-wine6-stable` | 是 `deepin-wine-diag` 的 `Depends`，本项目降为 `optdepends` |
| `deepin-elf-verify` | deb 的 `Depends`，Arch 无此包。已复核相关目录下 **0 处引用**，安全丢弃 |
| `libcapi20-3` | 同上。已复核**无任何 ELF 引用**它（wine 8/10/11 本体都没链） |
| `deepin-wine-staging`、`deepin-qt6platform-plugins` | 引擎声明的**可选**依赖，未装 |

---

## 目录结构

```
deepin-wine-arch/
├── gen/
│   ├── fetch-debs.py          按索引从商店源下载 deb 并校验 SHA256
│   ├── gen-pkgbuilds.py       由 deb 的 Depends 生成 PKGBUILD（含依赖映射表）
│   ├── build-all.sh           按依赖序批量构建
│   └── audit-vs-upstream.py   证明移植与上游一致（版本 + 逐文件 SHA256）
├── pkg/
│   ├── <9 个上游包>/PKGBUILD
│   ├── deepin-wine-builder/deepin-wine-builder.install   MIME 注册/卸载钩子
│   ├── deepin-wine-builder-qt6compat/                    Qt6 垫片（本项目新增）
│   └── libyaml-cpp07/                                    补 Arch 缺失的旧版 so
└── makepkg.conf               快速打包配置（zstd -3、!strip）
```

---

## 卸载

```bash
sudo pacman -Rns deepin-wine-builder deepin-wine11-stable deepin-wine10-stable \
  deepin-wine-runtime deepin-wine-extras deepin-wine-helper deepin-wine-logtool \
  deepin-wine-diag deepin-wine-builder-qt6compat libyaml-cpp07
```

`.install` 的 `post_remove` 会刷新桌面缓存并提示手工清理 MIME 关联
（安装脚本以 root 运行、拿不到用户 `HOME`，所以真正的用户级清理只能手动做）：

```bash
# 查看并清理 ~/.config/mimeapps.list 里指向引擎的行
grep -n deepin-wine-builder ~/.config/mimeapps.list
```

---

## 已知限制

- **只处理 x86_64**。引擎自带的 32 位运行时能跑 32 位程序，但本项目不提供 `lib32-*` 打包。
- `deepin-wine-staging`、`deepin-qt6platform-plugins` 未移植（引擎的可选依赖）。
- 打包脚本跟随上游版本；上游一更新，需要重跑 `fetch-debs.py` 与 `gen-pkgbuilds.py`
  （PKGBUILD 里的 `sha256sums` 会随之变化）。
- 上游 `deb` 文件名里的 Debian revision（如 `4.0.2+v25-1`）与 Arch 的 `pkgver`
  （`4.0.2+v25`）不是一回事，Arch 的 `pkgver` 不允许含 `-`。比对版本时请注意。

---

## 许可

本仓库中由 **SpiritHerb** 编写的脚本与源码采用 **MIT** 许可，见 [LICENSE](LICENSE)。

通过脚本下载并重新打包的第三方软件**不在 MIT 覆盖范围内**，其版权归统信软件技术有限公司
及各上游权利人所有，本项目不再分发其二进制。详见 [NOTICE.md](NOTICE.md)。

---

## 致谢

- **统信软件技术有限公司** —— deepin-wine 与 Windows 应用兼容引擎的上游作者；
- **Wine 项目** 及 DXVK / VKD3D-Proton / Wine-Gecko / Wine-Mono 的各位作者；
- **Arch Linux / AUR 社区** —— `dtk6*` 与 `deepin-qt6integration` 等依赖由 AUR 提供。

本项目由 **SpiritHerb**（[@spiritherb02](https://github.com/spiritherb02)）制作。
