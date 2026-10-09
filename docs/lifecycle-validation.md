# 生命周期重构验证记录（2026-10-08）

Ruff lint/format 通过；40 条框架测试通过；92 个参数化用例收集成功。

| 运行 | 用例数 | 失败 | 错误 |
|---|---:|---:|---:|
| lifecycle-ios | 26 | 0 | 0 |
| lifecycle-android | 26 | 2 | 0 |
| lifecycle-ios-settings | 5 | 0 | 0 |
| lifecycle-parallel-final | 12 | 0 | 0 |

Android 首轮两处失败：设置导航的共享文本造成就绪误判（已改为设置页独有标识，双平台相关复测通过）；推荐接口一次 unknown 异常导致 data_load_failed（保留原始证据，后续复测通过，不代表网络根因已修复）。

最初启动前 Android 模拟器不在线的一轮验证被中止；启动并恢复 ADB 连接后重新运行，未将环境错误算入通过结果。

最终双 worker 复测：每个设备只归属一个 worker，执行时间范围重叠。框架自动管理的服务分别使用 4723、4724 端口。

账号服务、真实登录适配器和跨机器租约后端未实现，本次验证不包含真实登录。

并行复测报告：`make open-report ARTIFACTS=artifacts/lifecycle-parallel-final`
