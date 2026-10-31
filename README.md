<div align="center">

<img src="logo.png" alt="天体位置查询" width="160" />

# 天体位置查询

为大语言模型注册 `get_celestial_position` 工具，查询当前时刻某颗天体的**高度角**和**方位角**。

[![Release](https://img.shields.io/github/v/release/inertialobs/astrbot_plugin_celestial_position?style=flat-square)](https://github.com/inertialobs/astrbot_plugin_celestial_position/releases)
[![Stars](https://img.shields.io/github/stars/inertialobs/astrbot_plugin_celestial_position?style=flat-square)](https://github.com/inertialobs/astrbot_plugin_celestial_position/stargazers)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue?style=flat-square)](LICENSE)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.17.0-5B8DEF?style=flat-square)](https://github.com/AstrBotDevs/AstrBot)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Last commit](https://img.shields.io/github/last-commit/inertialobs/astrbot_plugin_celestial_position?style=flat-square)](https://github.com/inertialobs/astrbot_plugin_celestial_position/commits/main)

</div>

## 功能

- 输入天体名称，返回高度角、方位角、方位（N/NE/E/...）、UTC 与本地时间、是否在地平线以上。
- 太阳系天体使用 astropy 内置星历计算，恒星和深空天体使用随插件发布的本地星表，常用目标无需联网。
- 观测点位置通过插件配置设置，支持南北半球和任意经度。

## 安装

在 AstrBot WebUI 的「插件 → 插件市场」中搜索安装，或通过仓库地址安装：

```text
https://github.com/inertialobs/astrbot_plugin_celestial_position
```

插件依赖写在 `requirements.txt` 中，AstrBot 安装/加载插件时会自动执行 `pip install`。如果自动安装失败，可手动安装：

```bash
pip install -r requirements.txt
```

## 配置

在插件配置中设置观测点：

| 配置项 | 类型 | 说明 |
| --- | --- | --- |
| `latitude` | float | 纬度，北纬为正，范围 -90 ~ 90 |
| `longitude` | float | 经度，东经为正，范围 -180 ~ 180 |
| `elevation` | float | 海拔，单位米 |
| `timezone` | string | IANA 时区名，例如 `Asia/Shanghai`，仅用于显示本地时间 |

## 使用示例

用户可以直接用自然语言询问：

```text
火星现在在哪个方向？
M31 现在能看到吗？
alpha And 的高度角是多少？
```

大模型会调用 `get_celestial_position`，返回类似：

```text
Object: Mars
Observer: latitude 31.3000 deg, longitude 120.5000 deg, elevation 15.0 m
Time (UTC): 2026-11-01 12:00:00
Time (Asia/Shanghai): 2026-11-01 20:00:00
Altitude: 42.15 deg
Azimuth: 231.40 deg (SW)
Status: above the horizon (visible)
```

## 支持的天体名称

- 太阳系天体（离线，内置星历）：`Sun`、`Moon`、`Mercury`、`Venus`、`Mars`、`Jupiter`、`Saturn`、`Uranus`、`Neptune`。
- 恒星（离线，本地星表）：专名（`Sirius`、`Alpheratz`）、拜耳命名（`alpha And`、`eps Eri`、`α And`）、弗兰斯蒂德编号（`21 And`）。
- 深空天体（离线，本地星表）：Messier（`M31`、`M42`）、NGC（`NGC 224`）、IC（`IC 434`），以及星表中已有的常用名（如 `Horsehead Nebula`）。
- 其他命名（如 `PGC 2557`、`UGC 1`）：通过在线 Sesame 服务解析，需要联网。

建议使用英文/拉丁名称。太阳系天体和本地星表命中时不联网。

## 项目结构

```text
astrbot_plugin_celestial_position/
├── main.py             # 插件入口与 LLM tool
├── metadata.yaml       # 插件元数据
├── _conf_schema.json   # WebUI 配置项
├── requirements.txt    # 依赖声明
├── star_catalog.json   # 本地恒星表
├── dso_catalog.json    # 本地 Messier/NGC/IC 星表
├── logo.png            # 插件图标
├── LICENSE             # GPL-3.0
├── NOTICE              # 星表数据署名
└── README.md
```

## 数据来源

`star_catalog.json`、`dso_catalog.json` 由
[HYG Database v4.1](https://codeberg.org/astronexus/hyg)（作者 David Nash）生成，
坐标采用 ICRS/J2000。星表只包含有专名、拜耳命名或弗兰斯蒂德编号的恒星，以及 Messier/NGC/IC 天体
（共 13,497 个深空天体）。

## 许可

- 插件代码：GNU General Public License v3.0 or later（GPL-3.0-or-later），见 `LICENSE`。
- 星表数据（`star_catalog.json`、`dso_catalog.json`）：CC BY-SA 4.0，见 `NOTICE`。
