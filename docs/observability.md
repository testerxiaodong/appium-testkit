# 可观测性与失败定位

## 记录的边界

框架记录自动化执行过程、设备证据，以及应用实际输出的日志。它不能通过 Appium
自动恢复应用未记录的 TLS/DNS 原始异常、HTTP 响应体或服务端 trace ID。
原始日志中的 `unknown` 会原样保留，不会自动解释成某一种网络故障。

## 文件组织

每次运行的 run ID 在 xdist 主进程生成并传给 worker。每次用例执行使用独立目录和
attempt ID，重复执行不会覆盖第一次失败的证据。

```text
artifacts/<run-id>/<device>/<test-id>-<unique-suffix>/
  events.jsonl                     所有阶段的结构化事件
  test.log                         可读的框架日志
  setup/ | call/ | teardown/
    failure.json                   原始异常、阶段、分类和关联字段
    screenshot.png                 可用时采集
    page-source.xml
    capabilities.json
    logcat.txt                     Android 有界日志缓冲
    app-log-excerpt.txt             Android 应用相关片段
    ios-system.log                 iOS 模拟器进程日志或真机 syslog
    appium-server-excerpt.log       本地服务器日志片段
    collect_kazumi_network.json     Kazumi 实际观察到的 HTTP 结果
    manifest.json                  可用文件、缺失原因、采集时间
  before-session-close/            session 关闭前的页面快照
```

关闭前快照在每个 session 结束时保留，因此后续 teardown 失败仍有页面证据。
它明确标记为较早的快照，不能当作 teardown 报错瞬间的画面。
创建 session 失败也有时间线和异常记录，manifest 会注明没有 driver。

设备日志是有界缓冲区，可能包含此前的应用 session；主机与设备时钟也可能不同。
用事件时间、应用 PID、Appium session ID 交叉定位，不把整段设备日志都归属于当前用例。
复用外部 Appium 服务时可能没有本地服务日志，manifest 会说明；客户端命令记录仍可用。

## 事件与 Allure

`events.jsonl` 每行一个 JSON，包含 UTC 时间、run/test/attempt ID、worker、设备、
平台、app ID、session ID、pytest 阶段和 step ID。

事件包括：

- 步骤开始、成功、失败和耗时；嵌套步骤带 parent step ID。
- Appium 命令名、定位器、耗时、错误类型。创建 session 单独记录步骤耗时。
- 应用安装版本的尽力采集；不能获取时明确标记 unavailable。
- 页面状态变化、已知弹窗发现/关闭验证结果、有限重试原因。
- 各 pytest 阶段结果和采集失败。

业务步骤同时显示在 Allure；失败阶段附上证据，结束阶段附上完整时间线。
当前更新弹窗用例等待不到弹窗会失败，不再自动跳过。插件仍保留历史条件跳过证据分支；其中的 `precondition_unverified` 不能解释为接口成功或确认没有更新。

```python
from appium_testkit.telemetry import event, step

with step("提交订单", expected_state="order_created"):
    # 执行业务动作并等待明确的结果，不盲目重放有副作用的操作
    event("page.state", state="order_created")
```

## 页面就绪条件

导航可见不等于业务数据已经加载。Kazumi 推荐页先检查目标数据和可见错误状态：
如果出现“暂时无法加载番剧”，立即抛出 `PageStateError`，
分类为 `data_load_failed`，而非继续等待番剧元素超时。

隐藏节点中的错误文案不会触发失败。没有足够 UI 证据时保持
`target_not_visible`，不擅自宣称是加载中、空列表或网络失败。
目前示例仍依赖真实热门榜和固定番剧；可观测性改善诊断，不能保证实时内容稳定。
稳定回归应使用约定的测试数据、测试环境或可控接口响应，真实在线依赖另做集成验证。

## 接入其他应用

在应用测试目录覆盖 `diagnostic_collectors` fixture，返回若干
`collector(evidence_directory) -> JSON可序列化对象`。
collector 只解析已经采集的证据；失败不会覆盖原始用例异常。
应用页面继承 BasePage，使用 `wait_for(condition, description)` 记录等待及预期。
应用自己的弹窗策略、页面状态和日志解析放在 `apps/<app>/`。

建议应用测试包提供以下结构化请求日志字段：
`timestamp, request_id, method, route, status, duration_ms, error_type,
raw_error_type, sanitized_error, stack, server_trace_id`。
Dio 应同时保留 `err.type`、`err.error`、`err.stackTrace` 的脱敏诊断；
仅打印 `err.message` 可能丢失根因。此框架不会修改或重建被测 App。

## 脱敏与保留

时间线不记录输入文字、完整命令参数或命令响应；已知凭证字段和常见文本形式进行脱敏。
截图不自动遮罩，XML/日志中的未知个人信息也不能保证全部去除。
使用测试账号，CI 对 artifacts 设置访问限制、保留期及容量限制，不公开上传。
目前本地证据保留到手动清理；没有隐式删除历史失败记录。

## 验证

`uv run pytest tests/unit` 包含日志脱敏、页面状态、采集降级及真实 pytest
setup/call/teardown/session 创建失败生命周期测试，不需要设备。

运行方式保持不变：`make android`、`make ios`、`make test-parallel`。
执行完 `make report` 和 `make open-report` 查看默认 Allure 结果。
自定义 `--alluredir` 时，生成报告需使用对应目录。

