# WireMock：可控更新弹窗

## 范围

WireMock 3.13.2 独立 Docker 服务，由 Testcontainers Python 管理生命周期，pytest 每个 worker 使用独立容器、动态端口。Python 通过标准库 HTTP 管理 API 注册规则，不依赖 WireMock Java SDK 或 Python SDK。电脑需要 Docker Engine 正常运行；本机无需安装 Java。

目前切换 Kazumi 更新接口 `/kazumi/v1/app/latest` 和测试构建的关键词搜索接口 `/v0/search/subjects`。其余 App 请求仍直连原服务，**没有代理整个 App，也不保证整个 App 离线可测**。WireMock 内有低优先级真实更新服务转发规则，测试注册高优先级覆盖。未命中覆盖的流量仍可能依赖上游。独立集成测试验证指定接口覆盖、其他请求转发、移除规则后恢复转发及异常退出清理。

## App 接入契约

Kazumi 必须使用包含 `TestLaunchConfig` 的本地源码构建，并传入：

```bash
flutter build apk --debug --target-platform android-arm64 --dart-define=KAZUMI_TEST_HOOKS=true
flutter build ios --simulator --debug --dart-define=KAZUMI_TEST_HOOKS=true
# 真机需要签名 Release 测试包
flutter build ios --release --dart-define=KAZUMI_TEST_HOOKS=true
```

生产构建不传此 define，默认忽略测试启动参数。不要将启用了 hooks 的包当作生产发布包。修改响应场景不需要重新构建。

- Android：启动 Intent string extra `kazumiTestUpdateBaseUrl`。
- iOS：启动参数 `--kazumi-test-update-base-url <origin>`。
- Flutter 在初始化网络客户端之前读取参数；只替换更新请求的 origin。
- 参数仅驻留当前进程，不写用户设置。为了确定性触发更新检查，提供测试更新地址时忽略已保存的自动更新关闭选项，但不修改它。因此这些用例**不验证自动更新开关的持久化语义**。
- 所有 Kazumi 设备用例（包括通用 smoke）关闭 Appium 自动启动，由 App 适配 fixture 先配置无新版本响应，再携带更新地址启动；重启也复用同一启动入口。
- 同一 worker、同一设备及同一安装包只显式安装一次，避免 noReset 保留旧包；首次启动用例的 reinstall 策略仍由框架执行。
- 普通用例不会点击关闭更新弹窗，也不在每次页面操作时查询它；更新业务用例通过 `update_scenario` 覆盖版本、延迟或状态码。测试结束验证指定规则确实收到请求，避免将网络失败误判为无更新；停留在首次引导的 smoke 除外。

请让 app matrix 指向新包。Android 本地默认路径是 `test-apps/Kazumi-android-arm64-debug.apk`，iOS 默认读取 Kazumi build 目录。仅构建源码而没有替换配置所指向的安装包不会生效。

## 运行

在 appium-testkit 根目录运行，模拟器需已启动：

```bash
make android ARTIFACTS=artifacts/android
make report ARTIFACTS=artifacts/android
make open-report ARTIFACTS=artifacts/android

make ios-simulator ARTIFACTS=artifacts/ios
make integration
```

更新弹窗属于普通业务回归，集中在 `tests/kazumi/test_update_notice.py`。`make android`、`make ios` 和 `make ios-simulator` 都包含这些用例。Kazumi 设备用例自动启动 WireMock 并使用无更新基线；`update_scenario` 覆盖具体业务响应，不需要额外开关。纯单元测试不会启动容器。缺少 Docker 或测试包时明确报错，不跳过。只有框架底层集成测试通过 `make integration` 单独运行。

同时运行两个模拟器：

```bash
uv run pytest --app-name kazumi --device android-primary --device ios-simulator \
  tests/kazumi/test_update_notice.py -n 2 --dist loadgroup
```

默认连接地址：pytest 控制端使用 `127.0.0.1`；Android 模拟器使用 `10.0.2.2`；iOS 模拟器使用 `127.0.0.1`。

真机示例（先构建对应测试包，确保局域网连通及测试 App 的网络权限）：

```bash
make ios PYTEST_ARGS='--wiremock-app-host 192.168.1.100'
```

上述 IP 仅为示例，请替换为设备可达的电脑 IP。指定 host 后容器端口绑定所有网卡，管理 API 也可达；仅在可信测试网络使用。远程 Appium 主机的路径、网络及设备接入没有在本轮验证。

## 用例

1. 返回 `tag_name=99.0.0`，观察弹窗、关闭；再次受控启动仍出现。
2. 延迟 15 秒返回新版本；先切换“我的”，再关闭弹窗，确认仍在“我的”。
3. 返回 `tag_name=0.0.0`，确认更新请求完成且没有更新弹窗。
4. 返回 HTTP 500，确认请求完成、没有更新弹窗且主导航可用。

无弹窗断言采用确认服务响应完成后的有界观察窗口，不声称无限期不会弹出。15 秒延迟用例若设备慢到来不及切换会真实失败，不自动跳过或扩大延迟掩盖。

## 分层与清理

- `appium_testkit/mocking`：HTTP 管理客户端、独立容器、可用性检查、规则 context manager。
- `apps/kazumi/mocking/update.py`：真实更新接口响应结构、原始上游地址、平台启动参数。
- `apps/kazumi/pytest_plugin.py`：普通用例的无更新基线、启动配置、安装缓存、请求证据和清理。
- `tests/kazumi/conftest.py`：页面准备及更新场景 fixture。

Allure 附件 `WireMock scenario and requests` 和用例证据目录下 `wiremock.json` 包含场景、匹配规则 ID、请求路径、状态与时间。请求证据只导出允许的字段，不保存请求头、查询参数或正文。场景数据应使用合成测试数据。

每条用例验证命中的具体规则 ID，防止误把线上弹窗当成 Mock 成功。用例结束停止 App，再清理规则、状态、请求记录；worker 结束删除自己创建的容器，不影响其他容器。

## 本轮验证（2026-10-09）

- Android API 36 模拟器：4 passed，153.91 秒。报告 `artifacts/wiremock-android-confirmed`。
- iOS 模拟器：4 passed，93.63 秒。报告 `artifacts/wiremock-ios-simulator-final`。
- Docker 真实服务集成：1 passed，验证覆盖、转发、恢复及失败清理。
- 框架单元测试：92 passed；Ruff lint/format、修改的 3 个 Dart 文件 analyze 通过。
- 真机本轮未验证，iOS 真机安装包未重新构建；需要按上面的 Release 命令构建测试包后再运行。

定位过程中修复了两个接入问题：`noReset` 可能保留同版本旧包，因此测试显式安装当前包；Android 启动使用 `component` 而非前置的位置参数 `intent`，确保 extras 被 Activity Manager 正确解析。每条用例必须匹配 WireMock 规则 ID，因此线上版本弹窗不会被误认为测试成功。
- 双 worker 并行运行 Android + iOS 模拟器：**8 passed，152.90 秒**。已观察到两个独立容器和不同动态端口。报告 `artifacts/wiremock-parallel`。

## 只运行更新弹窗业务

```bash
make android PYTEST_ARGS=tests/kazumi/test_update_notice.py
make ios-simulator PYTEST_ARGS=tests/kazumi/test_update_notice.py
```

上述验证记录对应接入时的运行结果。随后只整理了业务用例归属、fixture 名称和默认收集策略，没有重新运行设备用例。WireMock 是场景准备设施，测试文件和执行入口按业务组织。

### 普通用例的更新基线

普通用例固定返回 `tag_name=0.0.0`（无新版本），更新检查依然走真实网络客户端和业务解析。这样消除线上版本变化和迟到弹窗对其他业务的干扰，减少重复弹窗查询、关闭和安装。具体提速幅度尚未测量。本次基线生命周期调整仅做静态检查，尚未重新运行设备回归；上面的 8 passed 是此前接入版本的结果。

所有 Kazumi 设备用例现在都需要 Docker、带测试启动参数支持的安装包；真机还需要 `--wiremock-app-host`。测试服务器未准备好会明确失败，不回退线上更新接口。

## Testcontainers 容器管理

开发依赖与版本由 `pyproject.toml` 和 `uv.lock` 管理，执行 `uv sync --locked` 安装。
运行命令保持不变；先启动 Docker，再运行 `make android` 或 `make integration`。
Python Testcontainers 负责启动容器、查询动态端口和清理；WireMock HTTP 就绪检查仍由框架负责。
正常结束或 fixture 启动失败都会执行 `stop()`，Ryuk 资源回收容器提供进程退出后的辅助清理。
首次运行可能需要下载 Ryuk 镜像；受限网络需提前准备镜像。默认不禁用 Ryuk。
默认 WireMock 仅绑定本机回环地址；指定 `--wiremock-app-host` 后绑定所有网卡，供设备访问。
每个 worker 创建独立实例，不共享 reset 操作。当前仍自动创建容器，尚未提供连接已有远程 WireMock 的选项。
Docker 远程连接不等于手机可达：设备访问地址仍需单独配置。

验证入口：`uv run pytest tests/unit tests/integration --run-integration -q`。

## 搜索 UI 回归的受控响应

带 `KAZUMI_TEST_HOOKS=true` 的包在有测试服务地址时，将 POST `/v0/search/subjects` 路由到同一 WireMock。
搜索 fixture 按 `$.keyword` 精确匹配并断言 mapping 命中；ID 查询和详情请求仍直连原服务。
未配置搜索规则时使用现有上游代理，可能遇到真实服务鉴权失败；不应将其视为合法空列表。
生产构建不启用该路由。测试响应是固定 UI 数据，不代表真实搜索接口可用性。
