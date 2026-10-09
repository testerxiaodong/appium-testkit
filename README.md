# Appium Testkit

**面向 Android / iOS 的 Python + pytest 自动化测试脚手架。**

A Python Appium starter focused on explicit test state, device isolation, and failure evidence.

项目将通用执行机制与 App 页面、业务流程分开，使用 Kazumi 展示跨平台接入。适合作为个人工程作品、学习材料和团队项目的起点。当前是 **0.1 阶段的仓库模板**：尚未作为稳定的独立 Python 包发布，也不承诺生产级设备云能力。

## 能做什么

- App / 设备矩阵选择，Android UiAutomator2 与 iOS XCUITest。
- 本地 Appium 服务管理、每用例独立 Session、设备文件锁。
- pytest-xdist 按 App / 设备目标分组；独立端口支持多设备并行。
- 明确的重启、清数据、认证扩展、前置验证与逆序清理。
- 已知弹窗处理器，以及专门测试弹窗时的保留策略。
- Allure、JUnit、文本日志、JSONL 时间线及分阶段失败证据。
- WireMock + Testcontainers：每个 worker 独立容器，更新检查与关键词搜索可控。
- W3C 触屏手势、输入、滚动和前后台恢复操作。
- Ruff、锁定的 Python 依赖和无需设备的框架 CI。

**未实现：** 跨执行机设备/账号租约、账号池后端、通用登录实现、设备云集成、自动报告留存管理、独立 wheel 发布。登录与业务数据由 App 接入层实现。

## 快速开始

### 只看框架，不连接设备

需要 Python ≥ 3.12.4 和 [uv](https://docs.astral.sh/uv/)。在仓库根目录运行：

```bash
uv sync --locked
make quality
```

`quality` 包含 Ruff、框架单元测试（含 pytest 子进程检查）和移动用例收集。真实 Docker 集成测试另用 `make integration` 执行。没有本地设备配置时，收集使用占位目标，**不代表手机用例已经运行**。

### 运行手机用例

先安装 Appium、相应驱动及 Android SDK / Xcode，启动模拟器，然后配置本地文件：

```bash
cp config/devices.example.yaml config/devices.yaml
cp config/apps.example.yaml config/apps.yaml
# 编辑 devices.yaml：填写自己的 UDID
# 编辑 apps.yaml：填写实际包路径和 package / bundle ID
make smoke
make android
make ios                       # 默认 ios-primary 真机
make ios-simulator             # 只跑模拟器
```

**Kazumi 示例前提：** Docker 必须可用，容器由 Testcontainers 自动管理。示例依赖带语义标识和 `KAZUMI_TEST_HOOKS` 的定制 Kazumi 构建；直接下载上游安装包不能运行全部用例。本仓库不提供修改版应用源码或构建包，接入契约见 [语义标识](docs/semantic-identifiers.md) 和 [WireMock](docs/wiremock.md)。

App 安装包需要自行构建；仓库不包含 APK、IPA 或 .app。iOS 模拟器使用模拟器构建，真机使用正确签名的真机构建。完整套件含清数据场景，应选择专用测试设备。

详见 [快速开始](docs/getting-started.md) 和 [配置参考](docs/configuration.md)。

### 并行、日志和报告

```bash
make test-parallel              # 全部已配置目标
make ios-all                   # 所有 iOS 目标并行
make ios PYTEST_ARGS="-o log_cli=true --log-cli-level=INFO --durations=10"
make report
make open-report
```

自动管理服务时，示例 Android 使用 4723、iOS 使用 4724。每台设备的驱动端口也必须独立。共享外部 Appium 服务时由外部管理其存活，并传入 `--no-appium-service`。

## 目录与职责

```text
appium_testkit/          通用配置、pytest 插件、生命周期、观测与页面基础能力
apps/kazumi/            Kazumi 页面、组件、跨页流程和日志解析
tests/unit/             无需设备的框架测试，包含 pytest / xdist 子进程集成
tests/kazumi/           Kazumi 用例及应用 fixture
tests/test_smoke.py     通用启动/可访问性冒烟测试
config/*.example.yaml  可提交的安全模板
docs/                   设计、接入、排障与验证说明
artifacts/              本地产物，不提交 Git
test-apps/              本地安装包，不提交 Git
```

## 文档导航

| 文档 | 内容 |
|---|---|
| [文档索引](docs/README.md) | 推荐阅读顺序 |
| [架构设计](docs/architecture.md) | 分层、执行时序、设计取舍和限制 |
| [快速开始](docs/getting-started.md) | 环境、配置、运行、报告 |
| [模拟器与真机](docs/device-types.md) | 分类型选包、预检、能力筛选与 WDA |
| [配置参考](docs/configuration.md) | CLI、环境变量、markers、fixture |
| [接入新 App](docs/extending.md) | 页面、认证、测试数据、诊断扩展 |
| [应用状态](docs/app-state.md) | 重启、清理、认证、已知弹窗 |
| [可观测性](docs/observability.md) | 日志、截图、失败证据与脱敏边界 |
| [排障](docs/troubleshooting.md) | 设备、状态、网络、报告问题 |
| [验证记录](docs/lifecycle-validation.md) | 实际通过与失败结果，含复测 |
| [项目定位与已有方案](docs/ecosystem.md) | 与已有项目的关系及演进方向 |
| [发布准备](docs/publishing.md) | GitHub 首次发布检查 |

## 验证与限制

2026-10-08 的验证：40 条框架测试通过；iOS 全量 26 条通过；Android 首轮 24 通过、2 失败；修复设置页判断后，双平台相关用例并行复测 12 条通过。详细结果见验证记录；复测不能抹去先前的网络失败。

Kazumi 示例依赖实时服务和固定番剧名称，可能受到内容变化、更新接口和网络影响。当前观看用例覆盖详情入口及相关控件，**不代表已验证视频成功播放**。本地框架测试与外部依赖测试应分别看待。

设备锁目前仅支持 macOS / Linux，并且不能协调多台执行机。iOS 真机清数据策略不支持；登录扩展接口没有经过真实登录 App 的端到端验证。

## 贡献、来源与许可

- [贡献说明](CONTRIBUTING.md)
- [安全与敏感数据](SECURITY.md)
- [变更记录](CHANGELOG.md)
- [第三方说明](THIRD_PARTY_NOTICES.md)

本仓库原创框架和测试代码采用 [MIT License](LICENSE)。Kazumi 是独立第三方项目，本仓库不包含其应用源码或安装包，也不代表其官方测试套件。其源码和二进制遵循自身许可证。

### 可控更新弹窗（WireMock）

需要 Docker 运行中，以及启用 `KAZUMI_TEST_HOOKS` 的 Kazumi 测试包：

```bash
make android
make ios-simulator
```

更新弹窗业务用例包含正常更新、延迟弹窗、无新版本、HTTP 500 场景，默认纳入普通回归。fixture 自动准备响应，无需单独启用 Mock。所有其他 Kazumi 用例默认使用“无新版本”响应，避免更新弹窗干扰。
安装包构建、真机网络配置、报告和并行隔离见 [WireMock 接入说明](docs/wiremock.md)。

## 最近的定向验证

- 框架单元测试与真实 WireMock 容器集成：95 passed（接入 Testcontainers 时）。
- 搜索四条用例：Android 4 passed；iOS 模拟器 4 passed（分别运行）。
- 搜索关键词使用 Mock；ID 查询及详情附加数据仍依赖真实服务。
- 最近的 iOS 搜索布局修改已同步构建 Android 包，但该次修改后未重跑 Android。
- 以上不是最新全套、所有真机型号或设备云的兼容性认证。

[移动端操作与搜索用例](docs/mobile-actions.md)
