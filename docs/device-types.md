# 模拟器与真机

## 自动选包

```yaml
apps:
  - name: sample
    ios:
      app_id: com.example.sample
      simulator_app: test-apps/Simulator.app
      device_app: test-apps/Device.app
    android:
      app_id: com.example.sample
      app: test-apps/sample.apk
```

设备配置 is_simulator 必须是 YAML 布尔值。框架按设备类型选择 simulator_app 或 device_app；未配置该字段时回退到通用 app。Android 同样支持分类型配置，适合模拟器与真机使用不同 ABI 构建。显式 --app 或 APPIUM_IOS_APP / APPIUM_ANDROID_APP 会覆盖所有对应平台的变体，因此不要用它把同一个 iOS 包强行传给混合设备。

同时配置多个 iOS 目标后，--platform ios 会选择全部；--device 选择指定目标。示例矩阵名为 ios-simulator / ios-primary，分别用于模拟器和真机。

## 运行前检查

```bash
uv run pytest tests/test_smoke.py --app-name sample --platform ios --preflight-only
```

检查所选且适用的目标，不创建 Session：

- 本地包路径存在；Android 为含 AndroidManifest.xml 的 APK。
- iOS .app / .ipa 的 Info.plist 平台与设备类型一致。
- iOS Bundle ID 与配置一致。
- 真机包有描述文件，未过期、包含目标设备或允许全部设备、匹配应用标识。
- 真机 .app 通过 codesign 验证；.ipa 只检查内嵌描述文件和元数据，未验证整个归档内的代码签名。

检查发生在用例收集完成后、任何 Session 创建前。同一收集进程对同一目标只检查一次，错误集中报告；xdist 的 worker 各自执行检查。--collect-only 不运行预检，以支持无设备 CI。

预检不是安装成功保证：不检查在线状态、Developer Mode、信任、WDA 编译、系统端口是否被占用，也不保证 Android 包 ABI 与设备兼容。iOS 签名检查需要 macOS 系统工具；远端服务不会替本机完成该检查。no_reset 为 true 时驱动可能保留已安装版本，配置的新包不等于必然重新安装。

## 用例能力

```python
@pytest.mark.requires_capability("clear_app_data")
@pytest.mark.app_state("clear_data")
def test_first_launch(driver): ...
```

目前公开能力为 clear_app_data：Android 真机/模拟器与 iOS 模拟器支持；iOS 真机不支持。现有 app_state(clear_data) 也会自动推导这一要求。首次安装场景可使用独立的 app_state("reinstall")，真机也可执行；重装后由 App 用例验证引导页，不能把重装等同于清除 Keychain/服务端数据。

不适用用例在创建 fixture 前明确跳过，原因含设备和能力名；不会把运行中失败改成跳过。要求整套用例都可执行时加 --strict-capabilities，能力缺失将直接报配置错误。没有实现真机清数据，不用“卸载”等价替代 Keychain/服务端数据的清理。

## 真机 WDA

设备 YAML 支持 xcode_team_id、wda_bundle_id、allow_provisioning_updates；APPIUM_XCODE_TEAM_ID 优先于 YAML 团队值。它们分别映射 xcodeOrgId / xcodeSigningId 和 updatedWDABundleId。

被测 App 签名和 WebDriverAgent 签名是两件事。需要有效的开发团队、设备配对/信任、Developer Mode 和可用的 WDA 签名配置。驱动仍可能因为签名、系统版本或信任失败；查看服务端日志，不以页面定位重试处理。

模拟器与真机并行时使用独立 Appium、WDA 转发和 MJPEG 端口。真机示例 WDA 使用 8120，避免与已有模拟器的 8100 监听冲突。配置校验只能发现配置内冲突，不能预留系统端口。

allow_provisioning_updates 默认 false。显式启用后通过驱动允许 Xcode 更新签名描述文件和设备注册，需要本机已登录的开发账号。它不会自动创建开发账号或绕过设备信任。真机默认开启 showXcodeLog，便于从服务端日志定位 WDA 构建错误。

## 真机运行耗时

设备字段 ios_wait_for_idle_timeout 映射 XCUITest 的 waitForIdleTimeout。默认不覆盖驱动设置；对于持续动画导致每次点击等待很久的 App，可以在测试设备配置中显式调小（当前 Kazumi 真机验证使用 1.0 秒）。减少系统空闲等待后，仍必须以页面/业务结果确认操作成功，不能用该参数代替显式等待。

make ios 默认只选择 ios-primary；make ios-simulator 只选择 ios-simulator；make ios-all 显式选择全部 iOS 目标并行。自定义名称用 make ios IOS_DEVICE=设备名，不要在 PYTEST_ARGS 中再追加 --device，重复该选项会选择多个设备。

### 排查慢在哪一层

先按 events.jsonl 的 command.completed 统计命令次数、duration_ms 总和与中位数，再区分会话创建、页面动作和证据采集。step 的时间包含子命令，不能与命令耗时相加。

本次真机定向验证中，clickElement 中位数约 2.48 秒；但 6 条用例仍读取了 62 次页面 XML，累计约 147 秒。当前弹窗检测每次读取页面树，现场采集也会读取页面树，因此调低 waitForIdleTimeout 不会消除全部开销。不要为了提速只在启动时检查一次更新弹窗：弹窗可能在后续导航中异步出现。

页面动作应先执行一次，再用独立的结果等待确认目标状态。不能将点击不断放进结果轮询中，也不能仅因点击耗时超过轮询期限就认定导航失败。设置入口额外检查可交互状态与连续两次位置稳定；结果仍由设置页独有元素确认。

Flutter iOS 真机的 Appium 原生测试应配置可独立启动的签名 Release/Profile 包。Debug 包可能安装成功，但启动后只显示必须通过 Flutter 工具或 Xcode 启动的提示。重装会暴露此前 noReset 保留旧安装所掩盖的包配置错误。
