# 桌面版打包

## 文件

| 文件 | 作用 |
|------|------|
| `app.py` | 桌面版入口：启动 service → NiceGUI native 窗口 |
| `法规拆分.spec` | PyInstaller 配置文件 |
| `build.bat` | 一键打包脚本 |

## 依赖

```
pip install pywebview pyinstaller
```

## 打包

```
cd packaging
build.bat
```

产物：`dist/法规拆分.exe`

## 运行

双击 `法规拆分.exe` — 桌面窗口打开，内嵌 FastAPI + NiceGUI，无需浏览器。

## 与 launch.py 的区别

| | launch.py | app.py |
|---|---|---|
| 窗口 | 浏览器 | 原生桌面 |
| 启动 | `python launch.py` | `.exe` 双击 |
| 依赖 | 用户需配 Python 环境 | 全内置 |
| 原有配置 | 不动 | 独立目录 |
