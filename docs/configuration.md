# 配置参考

配置源不是统一的“环境变量总覆盖 YAML”规则，以下顺序对应当前实现。

## 文件

- `config/devices.yaml`：设备、平台、服务地址与驱动端口。
- `config/apps.yaml`：命名 App、平台安装包与应用标识。
- 两者均不提交；安全模板以 `.example.yaml` 结尾。
- `.env.example` 仅供参考，框架不会自动加载 .env。使用 shell export 或 CI 环境变量。

## 设备字段

| 字段 | 说明 |
|---|---|
| name / platform / udid | 名称、android 或 ios、设备 ID；空 UDID 的设备不会选中 |
| server_url | Appium URL；本地服务可自动管理，远端需自行管理 |
| device_name / platform_version | 可选 capability |
| is_simulator | iOS 清理/权限策略依赖它，请准确配置 |
| no_reset | 默认 true，要求驱动保留应用状态，不等于会话永不过期 |
| system_port | Android UiAutomator2 端口 |
| wda_local_port / mjpeg_server_port | iOS WDA 与视频流端口 |
| xcode_team_id / wda_bundle_id | iOS 真机 WDA 团队与 Bundle ID；不负责被测 App 签名 |
| ios_wait_for_idle_timeout | 可选 iOS 系统空闲等待秒数，默认不覆盖驱动值 |
| command_timeout | 新命令超时，默认 120 秒；不是页面显式等待超时 |
| auto_grant_permissions | Android 安装/驱动阶段权限选项 |
| ios_permissions | iOS 模拟器权限映射，值使用引号包住的 YES / NO / UNSET |

账号和密码不属于设备矩阵。

## CLI

| 参数 | 用途 |
|---|---|
| --preflight-only | 校验所选适用目标的安装包，不创建 Session |
| --strict-capabilities | 能力不支持时报错，默认明确跳过不适用项 |
| --platform android/ios | 平台筛选 |
| --app-name NAME | App 筛选，可重复 |
| --device NAME | 设备筛选，可重复 |
| --device-matrix / --app-matrix | 更换配置文件 |
| --device-udid | 覆盖所选目标的 UDID；多目标时慎用 |
| --app | 覆盖安装包路径；多平台通常不应共用一个路径 |
| --appium-server-url | 覆盖所选目标服务地址 |
| --no-appium-service | 不自动启动本地服务 |
| --device-lock-timeout | 等待本机设备锁秒数，默认 0，忙时立即失败 |
| --app-state preserve/clear_data | 默认本地数据策略 |
| --artifacts-dir / --run-id | 原始证据根目录与运行标识 |

`--alluredir`、`--junitxml`、`-n`、`--dist` 属于 pytest 及其插件。

## 环境变量及优先级

| 配置 | 优先级从高到低 |
|---|---|
| 平台 | --platform → APPIUM_PLATFORM |
| UDID | --device-udid → YAML udid → APPIUM_ANDROID_UDID / APPIUM_IOS_UDID |
| 服务地址 | --appium-server-url → YAML server_url → APPIUM_SERVER_URL → localhost:4723 |
| 安装包 | --app → APPIUM_ANDROID_APP / APPIUM_IOS_APP → YAML app |
| 命令超时 | APPIUM_COMMAND_TIMEOUT → YAML command_timeout → 120 |
| iOS 签名团队 | APPIUM_XCODE_TEAM_ID |

YAML 中相对包路径以仓库根目录解析。没有环境变量覆盖 app_id 的接口。

## Markers 与 fixture

| Marker | 含义 |
|---|---|
| app(name), platform(name), device(name) | 绑定适用目标，不匹配项跳过 |
| mobile, smoke, regression | 测试分类 |
| app_state(policy) | 覆盖 CLI 数据策略；preserve 或 clear_data |
| app_launch(policy) | prepared_app 的进程策略；restart（默认）或 preserve |
| auth_state(state) | preserve / anonymous / authenticated |
| requires_capability(*names) | 声明能力要求，目前支持 clear_app_data |
| permission_state(policy, *services) | preserve / grant / reset；支持情况由平台决定 |
| preserve_overlays(*names) | 给 App 弹窗处理器传递保留清单 |
| update_notice_test | Kazumi 示例兼容标记，新 App 不应依赖它 |

| Fixture | 合约 |
|---|---|
| driver | 低层 Session，不保证首页或登录 |
| prepared_app | 重启 → prepare → auth → verify；结束执行已登记清理 |
| relaunched_app | prepared_app 的兼容别名 |
| app_state_provider | 默认 None；覆盖后提供 prepare 和 verify |
| auth_state_provider | 默认 None；覆盖后提供 ensure_state |
| diagnostic_collectors | 默认空列表；应用覆盖为证据解析函数列表 |
| target / test_logger / artifacts_dir | 当前目标、文本日志、独立用例目录 |

只使用 driver 时，app_launch 不会自动触发重启。auth_state 请求非 preserve 状态时会请求 prepared_app；请用明确 fixture 依赖管理后续页面操作。

分类型安装包、校验范围和签名边界见 [模拟器与真机](device-types.md)。
