# Kazumi 稳定语义标识

本地 Kazumi 源码通过 `Semantics(identifier: ..., child: ...)` 暴露原生测试标识。保留原有 label、点击行为和选择状态，标识不使用翻译文案或列表位置。

## 平台映射

- iOS：`accessibilityIdentifier`，测试使用 `AppiumBy.ACCESSIBILITY_ID` 精确查询。
- Android：`resource-id`，测试使用 `UiSelector.resourceId()` 精确查询，避免 Appium 给无包名前缀的 ID 自动补全。不是 descriptionContains。
- 公共构建器：`appium_testkit/pages/locators.py::native_test_id`。
- 定位器仍归对应 Page / Component；没有一个集中所有页面元素的大文件。

## 标识约定

| 页面 | 标识 |
|---|---|
| 手机竖屏主导航 | `kazumi.nav.recommendations / schedule / watchlist / my` |
| 追番筛选 | `kazumi.watchlist.filter.all / watching / planToWatch / watched / onHold / abandoned` |
| 设置入口、返回 | `kazumi.settings.entry / back` |
| 设置分类 | `kazumi.settings.category.<路由末段>`，如 `theme`、`keyboard` |
| 外观设置 | `kazumi.settings.dark_mode / color_scheme` |
| 引导 | `kazumi.onboarding.progress / primary / skip_rules` |
| 更新提示 | `kazumi.update.title / later` |
| 详情操作 | `kazumi.details.watch / follow / follow_compact` |
| 番剧卡片 | `kazumi.subject.<Bangumi ID>` |

动态内容以业务 ID 标识，不使用序号。现有推荐用例使用明确的番剧 ID（622288）精确定位，再断言标题与测试数据一致；榜单变化、内容不在屏幕内仍可能导致用例前置条件失败。

## 维护与验证

新增/变更标识时同时更新 App 与 Page。不要把 identifier 填进面向用户的 label。更新包后必须确保设备安装的是新包；旧包不会回退到模糊文字定位。

`test_navigation_identifiers_are_unique_and_keep_labels` 验证可见节点唯一性、原生 ID 和中文读屏标签。引导流程验证状态变化，导航/追番验证 selected 属性，设置验证独立页面元素。页面 XML 仍用于失败现场和业务内容断言；更新弹窗查询已改成 ID 查找。

系统权限弹窗属于 iOS，本地 App 无法给系统按钮增加 ID，仍由明确的系统弹窗规则处理。此次主导航 ID 针对手机竖屏底部导航；横屏 NavigationRail 需要单独适配与验证。

Flutter 官方映射说明：https://api.flutter.dev/flutter/semantics/SemanticsProperties/identifier.html


## 本轮验证（2026-10-09）

- 11 个修改过的 Dart 文件通过 Flutter analyze；git diff --check 通过。
- Ruff lint/format 通过，86 条框架单元测试通过。
- iOS 真机完整业务集：27 passed，385.24 秒，报告目录 `artifacts/semantic-ids-ios-real-verified`。
- iOS 模拟器完整业务集：27 passed，407.91 秒，报告目录 `artifacts/semantic-ids-ios-sim-final`。
- Android API 37.2 模拟器：最终一轮 11 passed 后设备离线；模拟器宿主进程退出码 139，日志包含图形上下文错误。不能计为完整 Android 通过。该轮报告目录 `artifacts/semantic-ids-android-verified`。
- 已使用本机现有 API 36 镜像创建独立 `Codex_Kazumi_API36` 模拟器，原 `Pixel_10_Pro` 未修改。首次调试授权完成后，最终完整业务回归 **27 passed、0 skipped，588.04 秒**；报告目录 `artifacts/semantic-ids-android36-final`。

回归过程中修复：推荐页面原先根据 XML 父节点可见性剪枝，忽略了实际可见的卡片；现在直接用业务 ID 查找。追番控件将 ID、标签及点击语义放到同一节点，并移除多余的英文 enum value，避免 Android 将其与中文 content-desc 合并。此项最终修正后重建三端包，iOS 真机及模拟器详情专项分别 1 passed（19.50 秒 / 23.92 秒），对应报告目录 `artifacts/semantic-ids-ios-real-label-final` 与 `artifacts/semantic-ids-ios-sim-label-final`。新增契约检查和首次启动结尾断言均使用弹窗守卫，避免迟到的更新提示遮挡页面。历史失败报告保留，未将失败改成跳过。

### 运行

```bash
make ios
make ios-simulator
make android
make open-report ARTIFACTS=artifacts/semantic-ids-android36-final
```

安装包已经重建。Android 使用项目 `test-apps/Kazumi-android-arm64-debug.apk`；iOS 配置仍指向 Kazumi 源码目录下 `build/ios/iphonesimulator/Runner.app` 和 `build/ios/iphoneos/Runner.app`，后者为签名 Release。复现时需要构建包含这些标识的 Kazumi 源码；未修改的上游包不满足本测试契约。
