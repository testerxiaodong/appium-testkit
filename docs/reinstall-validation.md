# 重装策略与定位器重构验证（2026-10-09）

## 改动

- 用例级 app_state("reinstall")，通过 fullReset=true / noReset=false 创建会话，不修改共享设备配置。现有签名和包类型预检、设备租约仍有效。
- Kazumi 首次启动改用重装，并显式等待引导页；不再以 iOS 真机不支持 clear_data 为由跳过。
- 固定及动态定位器归属对应 Page，通用构建与转义位于 appium_testkit/pages/locators.py。
- Kazumi 对已知中文无线数据系统弹窗选择“仅限无线局域网”，支持 preserve_overlays("wireless_data")；未知弹窗不会被默认接受。
- 修复 make ios-all 对包含空格和引号的筛选条件的传递。

## 静态与单元验证

Ruff lint 与 format 均通过；82 条单元测试通过（17.75 秒），覆盖重装能力参数隔离、定位器转义、未知系统弹窗不处理以及权限用例保留弹窗。

## 设备验证经过

1. 首次真机重装发现本地配置包为 Flutter Debug：安装成功，但页面提示不能独立启动。模拟器首次启动通过。
2. 将同一路径的真机包重新构建为签名 Release；重装不包含构建步骤，后续直接复用此包。真机实际进入引导，但首次出现的无线数据系统提示遮挡操作。截图显示系统提示，被测 App 的 XML 未包含提示，已增加独立系统 alert 处理。
3. 最终定向运行 artifacts/reinstall-final：模拟器首次启动、外观设置、启动检查共 3 条通过；真机 3 条均在 WDA 建立会话阶段出现 XCTDaemonErrorDomain Code=41 / Not authorized for performing UI testing actions，未进入用例。

4. 用户恢复 UI 自动化授权后，artifacts/reinstall-authorized 真机定向复测 3 条全部通过（71.28 秒）：重装首次启动、外观设置、应用启动。此前授权阻塞已解除。

最终真机与模拟器各 3 条定向用例通过；本轮没有重新运行完整业务集，Android 设备回归也不在本轮验证范围内。

真机最终报告：make open-report ARTIFACTS=artifacts/reinstall-authorized。
历史阻塞报告保留在 artifacts/reinstall-final。
