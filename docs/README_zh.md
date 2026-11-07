# Klipsch Flexus

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)
[![GitHub Release](https://img.shields.io/github/release/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/releases)
[![Last Commit](https://img.shields.io/github/last-commit/ilia-ae/klipsch_flexus.svg?style=for-the-badge)](https://github.com/ilia-ae/klipsch_flexus/commits/main)
[![License](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/badge-license-mit.svg)](https://github.com/ilia-ae/klipsch_flexus/blob/main/LICENSE)
[![Auto Discovery](https://img.shields.io/badge/Auto_Discovery-Zeroconf-44cc11.svg?style=for-the-badge)](#自动发现)

[![CodeQL](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/github-code-scanning/codeql)
[![Copilot](https://img.shields.io/badge/Copilot-Code_Review-8957e5.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/copilot-pull-request-reviewer/copilot-pull-request-reviewer)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

🌐 [English](../README.md) | [Русский](README_ru.md) | [Deutsch](README_de.md) | [Español](README_es.md) | [Português](README_pt.md) | [Français](README_fr.md) | [Italiano](README_it.md) | [Nederlands](README_nl.md) | **中文**  
🔒 **安全**：[安全策略](../SECURITY.md) | [安全评估报告](SECURITY_ASSESSMENT_CORE_300.md)

---

适用于 **Klipsch Flexus** 回音壁的 Home Assistant 自定义集成：通过**设备原生的本地 HTTP API** 控制，不依赖云端，没有延迟。

> ✅ **41 个实体**。所有写入命令都已在 2026 年版固件上实测通过（HMAC 签名），在待机状态下同样有效。`main` 分支上的每个提交都会先在本地测试，详见[测试结果](#测试结果)。

## 📸 仪表板（Dashboard）

一个完全由本集成实体驱动的自定义 Lovelace 仪表板：输入源、声音模式、夜间/对白增强、EQ 预设、Dirac 滤波器、音调（低音/中音/高音）、环绕声道电平和低音炮，全部通过本地 API 实时控制。

![Klipsch Flexus 仪表板](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/dashboard.png)

**所需的 HACS 组件**（均可通过 [HACS](https://github.com/hacs/integration) 安装）：

| 组件 | 仓库 | 用途 |
|------|------|------|
| Klipsch Flexus | [ilia-ae/klipsch_flexus](https://github.com/ilia-ae/klipsch_flexus) | 本集成，提供所有实体 |
| Mushroom | [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | 媒体播放器卡片 |
| button-card | [custom-cards/button-card](https://github.com/custom-cards/button-card) | 带动态样式的输入源/模式/EQ 按钮 |
| card-mod | [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | 高亮当前状态（CSS） |

📋 **完整的仪表板 YAML 和配色方案：** [docs/DASHBOARD.md](DASHBOARD.md)（英文）

### 支持的型号

| 型号 | 声道 | 特性 |
|------|------|------|
| **Flexus CORE 300** | 5.1.2 | Dirac Live、Dolby Atmos、13 个单元 |
| **Flexus CORE 200** | 3.1.2 | Dolby Atmos 天空声道（向上发声） |
| **Flexus CORE 100** | 2.1 | 虚拟 Dolby Atmos |

本集成不检查型号。任何通过 Google Cast 广播自身的 Flexus 回音壁都会被添加，所有型号使用同一套本地 API 和同样的 41 个实体。维护者在 CORE 300 上测试。如果您的型号没有某个硬件（例如 CORE 100 没有高度声道），对应的控制可能会报错。

> 回音壁必须**先在官方 Klipsch Connect Plus 应用中完成全部设置**：至少完整走完一次初始设置流程（Wi-Fi、固件更新、扬声器配对、Dirac 校准）。在 2026 年版固件上，这一步也会生成本集成写入所需的认证凭据。如果应用里的设置只做了一半，大多数命令都会因未授权而失败。本集成只负责之后的日常控制。

## ⚠️ 固件兼容性（2026 更新）

2026 年的一次回音壁固件更新（**Device Version `1.1.3.x`**，例如 `1.1.3.0x7cd294e`，Cast 版本 `20250512_0201_RC25`）在两个方面改变了本地 HTTP API：

1. **`setData` 现在要求使用带 JSON 请求体的 `POST`。** 旧的 `GET /api/setData?...` 会返回 `405 Strict HTTP required!`。**已在 v2.4.1 修复**，请更新集成。
2. **大多数 `setData` 写入现在需要认证**（`settings:/webserver/authMode = setData`）。受保护的写入会返回 `401 Forbidden` 和 `WWW-Authenticate: HMAC_SHA256_AES256`。**已在 v2.5.0 修复**，集成现在会自动为这些写入签名。

### 新固件上可用的功能

| 功能 | 状态 |
|------|------|
| 所有传感器/状态读取（`getData`） | ✅ 可用 |
| 音量、静音 | ✅ 可用 |
| 输入源、声音模式、夜间/对白、低音/中音/高音、EQ 预设、Dirac、低音炮和环绕电平、电源 | ✅ 可用（HMAC 签名，v2.5.0+） |
| LED、唇形同步、平衡、响度、请勿打扰、自动待机，以及另外 4 个开关 | ✅ 可用（签名；v2.5.8–2.5.9 加入），待机时同样可用 |

您可以在自己的设备上通过**下载诊断**查看每条命令的实时状态（`command_health` 部分，v2.4.2 加入）。它是只读的：对每条命令，它会显示该设置是否可读，以及自集成上次加载以来设备对写入的响应（`http_status`；如果设备要求签名，则显示 `needs_auth`）。

### 修复状态

✅ **已在 v2.5.0 解决：完整控制已恢复，无需用户操作。** 已实现 `HMAC_SHA256_AES256` 请求签名。每台设备的凭据由回音壁的 MAC 地址自动推导，所以**无需任何配置**，只需更新集成。从 **v2.5.9** 起，集成直接从设备本身读取 MAC（`settings:/system/primaryMacAddress`），结果稳定可靠，因此每台设备第一次就能解析成功（之前的设备注册表/ARP 发现方式保留为后备）。签名写入发送到设备的 HTTPS 端点；音量/静音仍然无需签名。

> 需要 `cryptography` 包（Home Assistant 已自带，所以已经存在；未列为 manifest 依赖）。

📖 **我们是如何逆向分析的**：完整的调查过程（blutter、Frida、WireGuard 中间人、“安全表演”拆解）见[现场报告](REPORT_en.md)（英文；另有[俄文版](REPORT.md)）。

旧固件（`1.1.3` 之前）不受影响，仍可通过旧的 `GET` 后备方式完整控制。

## 功能

### 媒体播放器
- **音量**：设置音量、逐级调高/调低、静音/取消静音
- **电源**：开启/关闭（网络待机）
- **输入源**：电视 ARC、HDMI、SPDIF、蓝牙、Google Cast。当流媒体应用（Spotify Connect、TIDAL Connect、QPlay）、USB 或 Dirac 校准处于活动状态时，输入源会显示它
- **声音模式**：电影、音乐、游戏、体育、夜间、直通、环绕声、立体声
- **播放控制**：播放/暂停、下一曲/上一曲
- **媒体信息**：标题、艺术家、专辑、封面、来源应用

### 声道电平（11 个滑块：9 个为 -6 至 +6 dB，2 个低音炮为 -12 至 +6 dB）

| 声道 | 说明 |
|------|------|
| 前置高度 | Dolby Atmos 前置高度扬声器 |
| 后置高度 | Dolby Atmos 后置高度扬声器 |
| 左侧/右侧 | 侧环绕扬声器 |
| 左后/右后 | 后环绕扬声器 |
| 有线低音炮/无线低音炮 | 有线低音炮输出（RCA）与无线低音炮（一个或两个，统一调节），-12 至 +6 dB |
| 低音/中音/高音 | 音调 EQ 控制 |

### 音频设置（选择实体）
- **EQ 预设**：平直、低音、摇滚、人声（另有“自定义”：在 HA 或 Klipsch 应用中修改低音/中音/高音后，或在应用中设置了自定义曲线后显示；无法在 HA 中选择）
- **夜间模式**：压缩动态范围，适合小音量收听
- **对白模式**：增强对白清晰度（3 级）
- **Dirac Live**：房间校正滤波器（从设备自动发现）
- **LED 亮度**：前面板 LED：关闭/暗/亮
- **空闲超时**：自动待机前的空闲时间：关闭/5/10/15/30 分钟

### 设置数值（数值实体）
- **唇形同步延迟**：手动音画同步（0–500 ms）
- **平衡**：左右平衡（−10…+10 dB）

### 开关（开关实体）
- **自动唇形同步**：自动音画延迟
- **EQ 旁路**：绕过均衡器
- **自动开关机**：自动开机/待机行为
- **响度**：小音量时的响度补偿
- **请勿打扰**：屏蔽通知/提示音
- **自动待机**：空闲时进入待机
- **界面提示音**、**更多声音模式**、**BLE 遥控器自动配对**、**固件自动更新**

> 以上所有设置在回音壁处于**待机**时也可以写入（设备会应用并保存）；集成会保持这些实体可用，并记住您设置的值，而不会把它改回去。

### 诊断
- **响应时间**：API 轮询耗时（毫秒），以及请求/失败计数
- **设备状态**：开启/待机/离线，附带解码器、输入源、声音模式信息
- **签名 MAC**：用于为 2026 年版固件写入签名的 MAC（方案、候选值、解析状态）
- **网络连接**：当前有线/无线接口、接口名称、MAC 来源
- **操作模式**/**扬声器测试**：只读的设备状态（仅显示，有意不提供控制）
- **扬声器延迟**（有线/无线低音炮、无线环绕）：只读，由设备自动校准
- **下载诊断**：导出完整的设备状态（设置 > 设备 > Klipsch Flexus > 下载诊断）。其中的 IP 地址、所有 MAC 地址、Wi-Fi BSSID、设备 ID 和流地址都会被隐去

### 翻译
完整的界面翻译，共 **9 种语言**：英语、俄语、德语、西班牙语、法语、意大利语、葡萄牙语、荷兰语、简体中文（`zh-Hans`）。所有实体名称、状态和配置界面都已翻译。

## 安装

### HACS（推荐）

Klipsch Flexus 已收录在 HACS 默认商店中，无需添加自定义仓库。

[![打开您的 Home Assistant，并在 HACS 中打开此仓库。](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ilia-ae&repository=klipsch_flexus&category=integration)

1. 点击上方按钮，在您的 HACS 中打开 Klipsch Flexus（My Home Assistant 链接），或者打开 **HACS** 搜索 **Klipsch Flexus**
2. 点击 **下载**，然后重启 Home Assistant
3. 回音壁应该会被**自动发现**，请查看通知
4. 或者前往 **设置** > 设备与服务 > **添加集成** > Klipsch Flexus

### 手动安装

1. 把 `custom_components/klipsch_flexus/` 复制到 HA 的 `config/custom_components/` 目录
2. 重启 Home Assistant
3. 通过 设置 > 设备与服务 添加集成

### 更新

更新集成后（无论通过 HACS 还是手动），请**重启 Home Assistant**：HA 在启动时加载集成的 Python 代码，所以新版本只有在重启后才会运行。修改**选项**或通过**重新配置**更改主机地址后，更改会立即生效，无需重启（配置条目会重新加载）。

### Beta 版本

新功能和修复会先以 **Beta** 版发布：即 GitHub 上标签为 `vX.Y.Z-beta.N` 的预发布版本。稳定版 `vX.Y.Z` 随后发布。HACS 只向主动开启的用户提供 Beta 版。如果您什么都不做，就会一直使用稳定版，也不会收到 Beta 版的通知。

获取 Beta 版的方法（HACS 2.x；下面使用英文名称，您的 HACS 可能显示为中文）：

1. 前往 **设置** > 设备与服务 > **HACS**，打开 **Klipsch Flexus** 服务条目（HACS 会为每个已下载的仓库创建一个）
2. 找到 **Pre-release** 开关（一个诊断实体）。它默认处于禁用状态：打开它，点击齿轮图标，打开 **Enabled**（启用）开关，然后点击 **Update**（更新）
3. 打开 **Pre-release**。HACS 现在会把最新的 Beta 版作为更新提供。如需立即检查，在 HACS 中打开 Klipsch Flexus，然后在 ⋮ 菜单中选择 **Update information**
4. 安装更新并重启 Home Assistant

要回到稳定版，关闭 **Pre-release** 即可。HACS 之后只会再提供稳定版，而您会继续使用当前的 Beta 版，直到下一个稳定版替换它。如需立即切换回去，在 HACS 中打开 Klipsch Flexus，选择 ⋮ > **Redownload** > **Need a different version?**，选择最新的、没有 *pre-release* 标记的版本，下载后重启 Home Assistant。

## 自动发现

回音壁会通过 **mDNS / Zeroconf**（Google Cast 协议）在网络中被自动发现。

回音壁通电后，Home Assistant 会检测到它并显示通知：
> 在 `192.168.1.100` 发现了 **Klipsch Flexus CORE 300**。要添加这台回音壁吗？

**工作方式：**
- 回音壁通过 `_googlecast._tcp` mDNS 服务以 `Flexus-Core-*` 广播自身
- 集成通过 `md`（型号）和 `fn`（友好名称）TXT 记录识别设备
- AirCast 代理设备会被自动过滤掉

如果自动发现不起作用（例如网络隔离），您随时可以通过输入 IP 地址手动添加集成。

## 配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 主机 | — | 回音壁的 IP 地址（必填） |
| 轮询间隔 | 15 秒 | 可在选项中设置（5–120 秒）。待机时集成始终每 60 秒轮询一次 |
| 设备 MAC | 自动检测 | 仅在选项中设置（可选）。覆盖用于为 2026 年版固件写入签名的 MAC；只有当音量/静音以外的命令失败时才需要（参见**签名 MAC** 诊断传感器） |

**提示：** 为回音壁分配静态 IP 或 DHCP 保留地址，可以让运行更稳定。

之后可以通过**重新配置**修改 IP 地址（设置 > 设备 > Klipsch Flexus > 重新配置）。

## 工作原理

回音壁在 80 端口提供本地 HTTP API：
- `GET /api/getData`：读取参数
- `POST /api/setData`：写入参数（JSON 请求体；旧固件使用 GET 后备方式）
- `GET /api/getRows`：列出结构化数据（Dirac 滤波器）

在 2026 年版固件上，HMAC 签名的写入改为发送到 `POST https://<IP>/api/setData`。

### 面向慢速设备的稳健设计

Klipsch Flexus 使用**单线程 HTTP 服务器**，一次只处理一个请求。本集成围绕这一限制构建：

| 机制 | 说明 |
|------|------|
| 请求串行化 | 所有 API 调用都经过 `asyncio.Lock`，没有并发请求 |
| 退避重试 | 写入（媒体控制除外）和电源探测会重试 2 次，间隔 0.5 秒；轮询读取不重试（使用缓存后备），连续两次超时会把本次轮询判定为离线 |
| 自适应超时 | 读取 8 秒，写入 10 秒，电源命令 15 秒 |
| 平稳降级 | 读取失败时回退到上次缓存的值 |
| 乐观更新 | 界面立即更新，并保持写入的值，直到下一次常规轮询把它读回（命令约 1 秒后的轮询会获取其副作用，例如切换输入源后的解码器）；待机时应用的值会被缓存，所以待机轮询不会把它们改回去 |
| **感知待机的轮询** | 先探测电源状态；设置后的第一次轮询即使在待机时也会完整读取一次。之后，待机轮询只发 1 个请求而不是约 40 个，保留缓存值，轮询间隔放慢到 60 秒。待机时设置仍然**可用、可控制**：设备会应用写入，集成会记住它们 |

## 实体

![Home Assistant 中的 Klipsch Flexus 设备页面](https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/main/docs/images/device-page.png)

*本集成在 Home Assistant 中的设备页面：设备信息、控制、配置（夜间/对白/EQ/Dirac/LED 及各开关）和活动日志。*

| 实体 | 类型 | 类别 |
|------|------|------|
| Klipsch Flexus CORE 300 | 媒体播放器 | — |
| 夜间模式/对白模式/EQ 预设/Dirac 滤波器/LED 亮度/空闲超时 | 选择（x6） | 配置 |
| 后置高度/左后/右后、前置高度、左侧/右侧 | 数值（x6） | 配置 |
| 有线低音炮/无线低音炮 | 数值（x2） | 配置 |
| 低音/中音/高音 | 数值（x3） | 配置 |
| 唇形同步延迟、平衡 | 数值（x2） | 配置 |
| 自动唇形同步、EQ 旁路、自动开关机、界面提示音、更多声音模式、BLE 遥控器自动配对、固件自动更新 | 开关（x7） | 配置 |
| 响度、请勿打扰、自动待机 | 开关（x3） | 配置 |
| 响应时间、设备状态、当前输入源、声音模式 | 传感器（x4） | 诊断 |
| 签名 MAC、网络连接 | 传感器（x2） | 诊断 |
| 操作模式、扬声器测试、有线/无线低音炮延迟、环绕延迟 | 传感器（x5，只读） | 诊断 |

**合计：41 个实体**（1 个媒体播放器 + 6 个选择 + 13 个数值 + 10 个开关 + 11 个传感器）

## 故障排除

| 问题 | 解决方法 |
|------|----------|
| 无法连接 | 确认回音壁与 HA 在同一网络中。可以试试：`http://<IP>/api/getData?path=player:volume&roles=value` |
| 实体不可用 | Klipsch 应用可能在同时轮询设备，关闭应用后重试 |
| 更新缓慢 | 在选项中增大轮询间隔（设置 > 设备 > Klipsch Flexus > 配置） |
| 音量/静音以外的命令失败 | 查看**签名 MAC** 诊断传感器。如果它没有显示已解析的 MAC（或显示的 MAC 不对），在选项中把回音壁的 MAC 填入**设备 MAC** |
| 集成无法加载 | 在 Home Assistant 日志中查找导入错误。确认 HA 版本为 2024.11 或更高 |
| 深色主题下看不到图标 | 更新到 v2.5.19 或更高版本并重启。深色主题图标随集成一起提供，需要 HA 2026.3 或更高版本；更早的 HA 版本会显示 HA brands 网站上的黑色图标 |

## 已知限制

- 每个集成条目对应一台回音壁（多台请分别添加为独立条目）
- 不支持多房间/无线环绕组管理（请使用 Klipsch Connect Plus 应用）
- 控制只使用原生 HTTP API，不使用 Cast 或 AirPlay 协议。Google Cast 是一个可选的输入源（从 Cast 应用开始播放）；AirPlay 不在设备的输入源列表中，所以不作为输入源提供（从 Apple 设备向回音壁串流不受影响）
- 初始设置必须在官方 Klipsch Connect Plus 应用中**完整**完成：至少完整走完一次初始设置流程（2026 年版固件的写入认证凭据就是这样生成的）

## 安全

安全策略和最佳实践见 [SECURITY.md](../SECURITY.md)。

**网络安全提示**：回音壁使用明文 HTTP，其本地 API 在局域网内实际上没有认证。旧固件完全不需要认证；2026 年版固件（`1.1.3.x`）对大多数写入进行签名（`HMAC_SHA256_AES256`），但这**并不是真正的安全边界**：凭据由设备自身的 MAC（设备无需认证就会公开它）加上整个产品线通用的硬编码常量推导而来，所以网络中的任何主机都能伪造签名。读取始终开放（参见[固件兼容性](#️-固件兼容性2026-更新)）。**请把回音壁放在受信任/隔离的网段中。** 完整分析见[安全评估报告](SECURITY_ASSESSMENT_CORE_300.md)（第 12 节）。

## 测试结果

[![pytest，当前 Home Assistant](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-latest.json)](TESTING.md#test-result-badges)
[![pytest，支持的最旧 Home Assistant](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/pytest-min.json)](TESTING.md#test-result-badges)
[![hassfest](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/hassfest.json)](TESTING.md#test-result-badges)
[![Molecule](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/molecule.json)](TESTING.md#test-result-badges)
[![签名的本地 CI](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/badges/signed.json)](https://github.com/ilia-ae/klipsch_flexus/tree/ci-results/evidence)
[![Verify signed local CI](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/local-ci.yaml)
[![HACS validation](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml/badge.svg)](https://github.com/ilia-ae/klipsch_flexus/actions/workflows/validate.yaml)

所有测试都在维护者的电脑上运行，而不是在 GitHub 上。前五个徽章显示 `main` 分支上最新一个通过验证的提交的签名本地运行结果（*Signed local CI* 徽章会显示它的短 SHA 和日期）。GitHub 只有在验证签名证据之后才会写入这些结果。*Verify signed local CI* 就是 GitHub 上的这项验证。*HACS validation* 是 HACS 对仓库的检查，在 GitHub 上运行。

您可以自己验证这些证据（需要 Python 3.11 或更高版本、git、OpenSSH）：

```bash
curl -fsSLO https://raw.githubusercontent.com/ilia-ae/klipsch_flexus/ci-results/allowed_signers
git clone https://github.com/ilia-ae/klipsch_flexus.git && cd klipsch_flexus
git fetch origin refs/notes/local-ci:refs/notes/local-ci
python3 -I scripts/verify_local_ci.py --sha "$(git rev-parse HEAD)" --allowed-signers-file ../allowed_signers
```

`allowed_signers` 中是维护者的公开签名密钥。请把它与 GitHub 为维护者列出的 SSH 签名密钥进行比对：`curl -s https://api.github.com/users/ilia-ae/ssh_signing_keys`。详情见 [TESTING.md](TESTING.md#test-result-badges)（英文）。

## 贡献者

感谢所有报告问题和提交修复的朋友：

- **Kevin Jilissen**（[@Kevinjil](https://github.com/Kevinjil)）：发现回音壁的音量范围是 0–50 而不是 0–100，并修正了换算（[#22](https://github.com/ilia-ae/klipsch_flexus/issues/22)、[#23](https://github.com/ilia-ae/klipsch_flexus/pull/23)）
- **G Johansson**（[@gjohansson-ST](https://github.com/gjohansson-ST)）：替换了已移除的 `STANDBY` 媒体播放器状态，使集成在 Home Assistant 2026.12+ 上继续正常工作（[#25](https://github.com/ilia-ae/klipsch_flexus/pull/25)）

查看[完整的贡献者列表](https://github.com/ilia-ae/klipsch_flexus/graphs/contributors)。

## 参与与支持

- **问题和想法**：[GitHub Discussions](https://github.com/ilia-ae/klipsch_flexus/discussions)。需要提供哪些信息，见 [SUPPORT.md](../SUPPORT.md)。
- **Bug**：使用 bug 表单提交 [issue](https://github.com/ilia-ae/klipsch_flexus/issues/new/choose)，并附上诊断信息。
- **安全问题**：请私下报告，见 [SECURITY.md](../SECURITY.md)。
- **欢迎提交 Pull Request**。[CONTRIBUTING.md](../CONTRIBUTING.md) 说明了如何测试您的改动，以及维护者如何验证。[TESTING.md](TESTING.md) 介绍了测试和签名的本地 CI。
- 所有参与者都须遵守[行为准则](../CODE_OF_CONDUCT.md)。

## 许可证

MIT，见 [LICENSE](../LICENSE)。
