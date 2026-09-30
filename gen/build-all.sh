#!/bin/bash
# 按顺序构建 deepin-wine 移植全套包。纯解包，不做 strip。
#
# 用法：先跑 gen/fetch-debs.py 把上游 deb 下到 debs/，再跑本脚本。
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PKGDEST="$ROOT/repo"
mkdir -p "$PKGDEST"

# 依赖序：被依赖的先建。
# deepin-wine-builder-qt6compat 必须在 deepin-wine-builder 之前（后者把它作为 depends）。
ORDER=(
  libyaml-cpp07
  deepin-wine-builder-qt6compat
  deepin-wine-runtime
  deepin-wine-extras
  deepin-wine11-stable
  deepin-wine8-stable
  deepin-wine10-stable
  deepin-wine-helper
  deepin-wine-logtool
  deepin-wine-diag
  deepin-wine-builder
)

fail=0
for p in "${ORDER[@]}"; do
  echo "############ 构建 $p ############"
  cd "$ROOT/pkg/$p" || { echo "!! 目录不存在"; fail=1; continue; }
  rm -rf src pkg
  if makepkg -f -d --nodeps --noconfirm --config "$ROOT/makepkg.conf" 2>&1 | tail -20; then
    pk=$(ls -1 "$PKGDEST"/${p}-*.pkg.tar.zst 2>/dev/null | tail -1)
    if [ -n "$pk" ]; then
      printf "  ✔ %s  %s\n" "$(basename "$pk")" "$(du -h "$pk" | cut -f1)"
    else
      echo "  ✘ $p 未产出包"; fail=1
    fi
  else
    echo "  ✘ $p 构建失败"; fail=1
  fi
done

echo
echo "==================== 结果 ===================="
ls -lh "$PKGDEST" 2>/dev/null
echo "exit=$fail"
