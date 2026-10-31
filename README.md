# astrbot_plugin_celestial_position

为大语言模型注册 `get_celestial_position` 工具，查询当前时刻某颗天体的**高度角**和**方位角**。

## 功能

- 输入天体名称，返回高度角、方位角、方位（N/NE/E/...）、UTC 与本地时间、是否在地平线以上。
- 观测点位置通过插件配置设置。
- 常用天体和星表离线解析，无需联网。

## 安装

在 AstrBot WebUI 的「插件 → 插件市场」中搜索安装，或通过仓库地址安装。

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

## 支持的天体名称

- 太阳系天体（离线，内置星历）：`Sun`、`Moon`、`Mercury`、`Venus`、`Mars`、`Jupiter`、`Saturn`、`Uranus`、`Neptune`。
- 恒星（离线，本地星表）：专名（`Sirius`、`Alpheratz`）、拜耳命名（`alpha And`、`eps Eri`、`α And`）、弗兰斯蒂德编号（`21 And`）。
- 深空天体（离线，本地星表）：Messier（`M31`、`M42`）、NGC（`NGC 224`）、IC（`IC 434`），以及星表中已有的常用名（如 `Horsehead Nebula`）。
- 其他命名（如 `PGC 2557`、`UGC 1`）：通过在线 Sesame 服务解析，需要联网。

建议使用英文/拉丁名称。太阳系天体和本地星表命中时不联网。

## 数据来源

`star_catalog.json`、`dso_catalog.json` 由
[HYG Database v4.1](https://codeberg.org/astronexus/hyg)（作者 David Nash）生成，
坐标采用 ICRS/J2000。星表只包含有专名、拜耳命名或弗兰斯蒂德编号的恒星，以及 Messier/NGC/IC 天体
（共 13,497 个深空天体）。

## 许可

- 插件代码：GNU General Public License v3.0 or later（GPL-3.0-or-later），见 `LICENSE`。
- 星表数据（`star_catalog.json`、`dso_catalog.json`）：CC BY-SA 4.0，见 `NOTICE`。
