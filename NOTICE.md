# 第三方软件声明 / NOTICE

## 本仓库不含任何上游二进制

本仓库**只包含打包脚本**（PKGBUILD、生成器、一个自编的 C++ 兼容垫片、文档）。
所有上游软件都由使用者运行 `gen/fetch-debs.py` 从**统信官方应用商店源**自行下载，
再本地构建。仓库中没有任何 `.deb`、`.pkg.tar.zst` 或其他二进制的再分发。

这样做的原因：

1. **版权**：上游二进制由统信软件技术有限公司发布，本项目无权再分发；
2. **体积**：单个 deb 最大约 218 MiB，超出 GitHub 100 MiB 的单文件上限。

## 上游软件归属

| 上游包 | 权利人 | 说明 |
|---|---|---|
| `deepin-wine-builder`（统信 Windows 应用兼容引擎） | 统信软件技术有限公司 | 版权归属统信 |
| `deepin-wine8-stable` / `deepin-wine10-stable` / `deepin-wine11-stable` | 统信软件技术有限公司 | 基于 Wine（winehq.org，LGPL-2.1+）的 deepin 分支 |
| `deepin-wine-helper` / `-runtime` / `-extras` / `-logtool` / `-diag` | 统信软件技术有限公司 | — |
| Wine-Gecko | Wine 项目 | MPL-2.0 |
| Wine-Mono | Wine 项目 | MIT |
| DXVK / VKD3D-Proton | 各自作者 | zlib / LGPL-2.1 |

各上游包的具体许可以其自带的版权文件为准（安装后可见于对应 `/opt` 目录下）。

## 本项目新增的部分（MIT，© 2026 SpiritHerb）

- `gen/` 下的下载、生成、构建、审计脚本
- 全部 PKGBUILD 与 `.install`
- **`pkg/deepin-wine-builder-qt6compat/`** —— 补 Qt6 ABI 断代的转发垫片（见 README）
- `makepkg.conf`

## 非官方声明

本项目**非官方**，与统信软件技术有限公司**无任何隶属或合作关系**。
「统信」「UOS」「deepin」等名称与商标归其各自权利人所有，本项目仅作描述性使用。

上游才是权威。遇到软件本身的功能问题请向统信反馈；**只有打包/移植相关的问题**
才适合提到本项目的 Issue 里。
