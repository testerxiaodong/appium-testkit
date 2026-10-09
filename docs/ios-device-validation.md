# iOS 真机与模拟器修复验证（2026-10-09）

## 问题与修改

- 原 make ios 仅筛选平台，设备矩阵加入真机后会同时运行两台。现在默认只选 ios-primary；make ios-simulator 只选模拟器；make ios-all 显式并行运行全部 iOS 设备。
- 原真机运行中 65 次点击累计 1331.4 秒，中位数约 20.48 秒。增加可选 ios_wait_for_idle_timeout；本地真机显式设为 1.0 秒后，定向复测 17 次点击中位数约 2.48 秒。此参数默认不覆盖驱动值。
- 主导航与追番筛选将动作执行和结果等待拆开，避免慢点击消耗结果等待预算；未增加失败重跑。
- 设置入口增加可交互与位置稳定检查，进入后以设置页独有元素确认。原模拟器失败日志没有弹窗处理事件，不能将该次失败归因为更新弹窗；过早点击是待验证的解释，此处通过加强前置条件防护。

## 验证结果

| 验证 | 结果 | 耗时 |
|---|---|---|
| Ruff lint / format | 通过，56 个文件格式合规 | — |
| 框架单元测试 | 69 passed | 18.05 秒 |
| 真机追番筛选定向复测 | 6 passed | 237.92 秒 |
| 模拟器设置定向复测 | 4 passed | 91.48 秒 |
| 完整 iOS 业务回归（双 worker） | 51 passed、1 skipped、0 failed | 893.96 秒 |

完整回归中，模拟器 26 条通过；真机 25 条通过，1 条首次启动用例因不支持 clear_app_data 在 fixture 前跳过。更新弹窗用例在两端均通过。Android 完整业务集不在此次验证范围内。

运行命令：

```bash
make ios-all ARTIFACTS=artifacts/ios-device-regression PYTEST_ARGS="-m mobile"
make report ARTIFACTS=artifacts/ios-device-regression
make open-report ARTIFACTS=artifacts/ios-device-regression
```

JUnit：artifacts/ios-device-regression/junit-parallel.xml。结构化事件及服务端日志：artifacts/20261008T220842Z-b1927898（目录时间使用 UTC）。

## 性能边界

本轮双设备耗时约 15 分钟，不能称为全面性能优化完成。真机 6 条筛选定向复测中 62 次页面 XML 读取累计约 147 秒，仍是主要开销。弹窗检查与现场采集保留了页面树读取；每条业务用例继续重启应用并确认就绪，保留隔离。步骤计时包含子命令，统计时不得相加。

本次是现有设备、安装状态和网络下的一轮回归通过，不代表所有机型或未来运行绝不会失败。签名、设备在线和外部服务变化仍需通过日志定位。
