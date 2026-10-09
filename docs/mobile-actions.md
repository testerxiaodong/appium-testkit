# 移动端操作分层

通用交互通过 `page.actions` 使用，定位器保留在 Page/Component，业务编排放 Flow，用例断言业务结果。

| 操作 | 使用场景 | API |
| --- | --- | --- |
| 替换输入 | 搜索、表单 | `replace_text(locator, value)` |
| 收起键盘 | 输入后访问被遮挡控件 | `hide_keyboard()` |
| 长按 | 上下文菜单、编辑模式 | `long_press(locator)` |
| 双击 | 明确支持双击的播放器或图片 | `double_tap(locator)` |
| 滑动 | 列表、轮播 | `swipe('up', container=locator)` |
| 有界滚动查找 | 屏幕外的设置项 | `scroll_to(locator, max_swipes=5)` |
| 前后台恢复 | 使用其他 App 后返回 | `background_and_resume(app_id)` |

手势采用 W3C touch pointer，不使用旧 TouchAction。方向表示手指方向，up 通常使列表展示更下面的内容。
滑动优先传入明确的容器；整屏比例坐标只用于没有可定位滚动容器的页面。
操作不盲目重试：长按、双击、提交等可能有副作用。完成操作后由 Page 或用例等待明确状态，不用固定 sleep 判断成功。
滚动最多执行给定次数，失败抛出 TimeoutException；截图和页面树由现有 pytest 证据链捕获。
输入值不写入操作步骤元数据；敏感字段仍应配合命令日志脱敏与截图策略，不能把此保证理解为所有证据都不含输入内容。
键盘关闭使用驱动原生能力；若特定 iOS 输入框需要 Done 按钮，应在对应组件封装，不能以任意点击屏幕代替。
前后台恢复只验证进程恢复到前台，业务层仍要断言路由/筛选保持。它不等价于杀进程后恢复。

Kazumi 示例：`tests/kazumi/test_resume_flows.py` 覆盖四个主标签、六个追番筛选、深层设置恢复及滚动定位。
恢复用例不会再次点击目标标签或筛选，以免掩盖状态丢失。
长按、双击、文本输入作为通用能力提供，未对缺少明确对应行为的 Kazumi 页面编造用例。

运行：

```bash
uv run pytest tests/kazumi/test_resume_flows.py --app-name kazumi --platform android
```

这些新增设备场景尚未运行验证；需可用模拟器或真机、Docker 和带测试钩子的 Kazumi 包。

## Kazumi 搜索与列表用例

`tests/kazumi/test_search_flows.py` 覆盖关键词命中指定条目、ID 搜索进入详情后返回、清空搜索、替换查询。
断言使用搜索结果卡片 ID 与卡片内标题，不能仅在全页查找关键词（输入框也包含关键词）。
关键词搜索使用 WireMock 按请求中的 keyword 精确匹配固定响应，并断言规则命中。ID 查询与详情附加数据仍请求真实服务，因此不是全离线测试。镜像搜索曾返回 HTTP 401；这些 UI 用例不用于证明线上搜索鉴权正常。
当前不把空结果作为通过条件，因为应用对部分接口失败和无结果的显示不足以区分两者。

本地 Kazumi 源码新增 `kazumi.search.result.<subject_id>` 语义标识和 `返回番剧列表` 按钮标签。
**必须重新构建并替换设备配置所指向的测试包**；旧 APK/IPA 不包含这些定位信息。
沿用现有构建方式及 `--dart-define=KAZUMI_TEST_HOOKS=true`，Android 包复制到配置路径，iOS 使用对应模拟器/真机产物。
设备运行结果见后续验证记录。

```bash
uv run pytest tests/kazumi/test_search_flows.py --app-name kazumi --platform android
```
