# 快速开始

## 环境

| 项目 | 要求 |
|---|---|
| Python | ≥ 3.12.4；依赖版本以 uv.lock 为准 |
| uv | 安装与执行 Python 依赖 |
| Appium | 自行安装服务端和目标平台驱动；不由 uv 安装 |
| Android | Android SDK、adb、在线模拟器或真机 |
| iOS | macOS、Xcode、模拟器或已完成签名配置的真机 |
| 报告 | 运行测试需要 allure-pytest；生成网页另需 Allure CLI 及其运行环境 |

版本兼容性以 [Appium 安装说明](https://appium.io/docs/en/latest/quickstart/requirements/) 和各驱动要求为准，不能把任意最新版本组合视为经过本仓库验证。

## 1. 安装依赖

在仓库根目录：

```bash
uv sync --locked
make help
make quality
```

make 命令会移除其他项目遗留的 VIRTUAL_ENV，使用当前目录的 .venv。没有设备时可以执行 quality；收集占位项不代表移动端通过。

## 2. 配置本地设备和应用

```bash
cp config/devices.example.yaml config/devices.yaml
cp config/apps.example.yaml config/apps.yaml
adb devices
xcrun simctl list devices booted
appium driver list --installed
```

按实际平台执行上述检查。把 UDID 写入 devices.yaml，应用路径和真实 package/bundle ID 写入 apps.yaml。模板中的 `com.example.kazumi` 是占位值。安装包相对路径以仓库根目录解析。

只测试 Android 时可以只保留 Android 配置。iOS 模拟器 .app 与真机 .app/.ipa 不是可互换的构建；本项目不负责构建或签名被测 App。

## 3. 从小范围开始

```bash
make smoke PYTEST_ARGS="--platform android"
make android PYTEST_ARGS="-k primary_navigation"
make ios PYTEST_ARGS="-k test_update_notice"
make android
make ios                       # ios-primary 真机
make ios-simulator             # ios-simulator 模拟器
```

完整平台目标也会运行框架单元测试。只运行设备用例：

```bash
make ios PYTEST_ARGS="-m mobile"
```

更新弹窗专用测试要求已完成初始化、开启更新检查且服务端确实有新版本；未满足条件会失败，不能把它当作随时必过的通用冒烟测试。

## 4. 并行与日志

```bash
make test-parallel
make ios PYTEST_ARGS="-o log_cli=true --log-cli-level=INFO --durations=10"
```

示例服务端口为 Android 4723、iOS 4724，驱动端口也要独立。只配置一个设备时，增加 worker 不会让同一台设备并发操作。

终端 INFO 日志与 events.jsonl 不等价：结构化命令时间线仍保存在文件中。`-s` 只影响输出捕获，不等价于开启 INFO 日志。

## 5. 报告

```bash
make report
make open-report
```

保留独立报告目录：

```bash
make ios ARTIFACTS=artifacts/demo PYTEST_ARGS="--artifacts-dir=artifacts/demo"
make report ARTIFACTS=artifacts/demo
make open-report ARTIFACTS=artifacts/demo
```

`ARTIFACTS` 控制 Makefile 的 Allure/JUnit 目录；`--artifacts-dir` 控制 kit 的每用例原始证据目录。只设置前者时，原始证据仍默认位于 artifacts 下。

默认命令使用 --clean-alluredir；不要让两个独立 pytest 进程同时写同一 Allure 结果目录。使用一次 xdist 运行或各自分配目录。
