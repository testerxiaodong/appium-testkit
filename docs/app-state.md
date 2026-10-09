# 应用状态与生命周期

`driver` 是低层 Session fixture，不承诺登录、首页或重启。
业务用例使用 `prepared_app`；默认保留应用数据并重启进程。
`relaunched_app` 是兼容别名，同一条用例请求两个 fixture 只执行一次准备。

顺序：设备锁 → 清理策略 → 创建 Session → 权限策略 → 重启 → provider.prepare → 认证 → provider.verify → 用例 → 逆序清理 → 关闭 Session → 释放设备锁。

- `@pytest.mark.app_state("clear_data")`：现有本地数据清理策略；Android 和 iOS 模拟器支持，iOS 真机在收集后标记为能力不适用；--strict-capabilities 可改为报错。不是 Keychain、服务端数据或系统权限的全面重置。
- `@pytest.mark.app_launch("preserve")`：prepared_app 不主动重启进程，不能阻止驱动在创建 Session 时自身的启动行为。
- `@pytest.mark.auth_state("authenticated")` / `anonymous`：要求应用提供 auth_state_provider，其 ensure_state 必须建立并验证目标身份；未配置时 setup error。

## App 接入扩展

在应用自己的 conftest.py 覆盖 app_state_provider，返回含 prepare(driver, target, cleanup) 和 verify(driver, target) 方法的对象。参数按关键字传递。

prepare 负责可重复执行的业务数据准备，verify 验证约定状态。修改资源前用 cleanup.register("操作名", callback) 登记补偿，callback 不接受参数，可使用闭包。不能假定上一条用例清理成功。

清理逆序执行，每个回调即使失败也继续其他回调；正常用例的清理失败报告 teardown error。准备失败时仍清理，原始异常保留，附加清理失败说明，详细步骤写入事件日志。

认证位于准备之后、验证之前。必须使用显式 fixture 依赖建立额外步骤顺序；不要另写一个无依赖 autouse fixture 重启应用或登录。

Kazumi main_page 和更新弹窗测试均使用公共重启 fixture。首次启动测试仍使用 clear_data + driver，保留引导页面；通用框架不自动完成引导。

账号租约、服务端数据重置以及跨机器资源服务尚未实现；这些接口不意味着存在相应后端。

## 已知弹窗

OverlayHandlers 接收名称到回调的映射，按顺序同步执行。回调必须仅处理明确识别的弹窗，并验证关闭成功；异常原样抛出。没有后台线程，也不会任意点击未知对话框。

`@pytest.mark.preserve_overlays("update_notice")` 在 Driver 上声明保留项。应用适配器把 preserved_overlays 传给处理器；Kazumi 页面操作已接入。专门验证弹窗的测试直接操作组件。

## 并行运行

使用 `-n 2 --dist loadgroup`。设备分组标记必须先于 xdist 收集处理写入，否则设备锁虽能防止同时占用，但用例会在 worker 间移动。

框架自动管理 Appium 时，每个并行设备配置独立 server_url 端口，示例 Android 4723、iOS 4724；同时保持 systemPort/WDA/MJPEG 端口独立。若共用外部管理的服务，预先启动并使用 `--no-appium-service`，由外部负责整个运行周期的服务存活。

## 用例级重新安装

`@pytest.mark.app_state("reinstall")` 在该用例创建 Session 时使用 `fullReset=true`、`noReset=false`，由驱动卸载并安装配置的包；Android 与 iOS 真机、模拟器均可请求此策略。未标记用例保持原来的策略，目标配置对象不会被修改。也可使用 `--app-state=reinstall` 作为默认值，但标记优先，整套重装会增加耗时。

安装包在 Session 前经过现有预检，操作在设备租约内执行，重装阶段写入日志及 Allure 步骤。驱动可能在 Session 结束时移除被测应用；后续用例仍由正常 Session 安装流程恢复。重装失败按 setup error 报告，不改为 skip。

重装不承诺清空 Keychain、云端或服务端数据。App 适配层必须断言所需初始状态；Kazumi 首次启动用例等待引导页，未出现则失败并采集证据。`clear_data` 仍保留原有平台限制，不自动偷偷替换为卸载操作。

### 重装后的系统权限提示

Kazumi 适配器通过独立的 iOS alert 接口识别包含 Kazumi 与“使用无线数据”的系统提示，并按名称选择“仅限无线局域网”。该提示可能不会出现在被测 App 的页面树中；截图与系统 alert 查询是不同证据。未知提示不自动接受；匹配提示缺少指定按钮时失败。专门测试此权限时使用 `@pytest.mark.preserve_overlays("wireless_data")` 保留提示。其他系统语言需要显式新增对应规则。

重装复用已构建的包，不会运行 Flutter/Xcode build。本地真机已改用签名 Release 包，避免 Flutter Debug 启动限制；仅应用代码、构建设置或签名变化时重新构建。
