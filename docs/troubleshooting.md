# 排障指南

先看失败阶段和原始异常，再看页面树、截图与时间线。不要只看到 TimeoutException 就增加等待时间。

| 现象 | 优先检查 |
|---|---|
| uv 无法启动 pytest | 是否在仓库根目录执行过 uv sync --locked；make 会忽略别的项目的 VIRTUAL_ENV |
| 没有目标 | 配置文件是否存在、UDID 是否为空、App/平台筛选是否匹配 |
| Android offline / unauthorized | adb devices；等待启动、确认授权或重连；不是页面定位问题 |
| iOS Session 创建失败 | 模拟器是否在线、构建平台是否匹配、XCUITest/WDA、真机签名 |
| 设备锁冲突 | 是否有另一测试进程使用同设备；不要通过删锁文件绕过活跃持有者 |
| 端口冲突或互相断开 | 每个托管服务独立端口；共享外部服务使用 --no-appium-service |
| 登录用例前已登录 | 是否误用了 authenticated fixture；登录测试应显式准备 anonymous |
| 下一条受深路由影响 | 是否请求 prepared_app，以及业务页面是否验证起始状态 |
| 更新弹窗漏处理 | 看 overlay 事件；启动后异步出现需在操作边界检查 |
| 更新测试超时 | 确认确实重启、没有自动关闭、更新条件成立；不能直接 skip |
| 接口失败但报元素超时 | Page 应识别可见错误状态；原始 unknown 不足以断言 TLS/DNS 根因 |
| 返回动作不稳定 | 就绪条件是否为两个页面共有文本；确认实际路由和唯一标识 |
| 终端没有 INFO 日志 | 加 -o log_cli=true --log-cli-level=INFO；结构化事件查看 events.jsonl |
| Allure 没截图 | 查看失败阶段目录和 manifest；Session 未创建时无法截图 |
| 报告不是刚才的结果 | Allure 结果目录与生成/打开目录是否一致；重新 make report |
| 并行命令仍像串行 | 必须 --dist loadgroup；检查 worker 与设备归属、Session 时间区间 |

## 避免掩盖问题

不要因失败自动把测试标成 skip；不要对未知弹窗随意点击；不要在业务中途重新登录后继续断言；不要删掉首轮证据只展示复测通过。

框架输出 setup/call/teardown；清理错误可与业务失败同时存在。看完整异常与事件，不能仅按最后一行判断根因。

## 提交问题所需信息

附最小命令、Python/Appium/驱动版本、平台、测试阶段、脱敏后的异常及 manifest。公开 issue 不附账号、设备标识、完整原始日志和未审查截图。私人数据问题见根目录 SECURITY.md。
