# 接入另一个 App

## 1. 配置与目录

在本地 apps.yaml 增加配置，例如 name 为 shop，填写实际包路径及标识。创建 `apps/shop/` 和 `tests/shop/`，并在测试模块声明：

```python
import pytest

pytestmark = pytest.mark.app("shop")
```

先运行 `uv run pytest tests/test_smoke.py --app-name shop --platform android`，确认基础安装和可访问性正常，再编写业务页面。

## 2. 页面、组件与 Flow

```python
from appium_testkit.pages.base_page import BasePage


class HomePage(BasePage):
    def wait_until_ready(self):
        self.find_accessibility_element("home_ready")

    def open_cart(self):
        self.tap_accessibility_element("open_cart")
```

示例 ID 需要应用真实提供；不会自动生成。优先使用稳定 accessibility ID；跨平台无法统一时在页面层区分，避免业务测试到处判断平台。

Page 表达页面动作；Component 表达复用 UI；Flow 组合多个页面。只有真正需要跨页复用时再创建 Flow，避免给每个按钮增加一层类。

## 3. 明确起始页面

```python
@pytest.fixture
def home(prepared_app):
    page = HomePage(prepared_app)
    page.wait_until_ready()
    return page
```

重启不等于首页已经渲染，也不等于数据已经加载。验证页面独有标识、目标数据或明确错误状态；不要以两个页面共有的文字判断导航结束。

## 4. 认证接口

覆盖 `auth_state_provider`，返回对象，实现：

```python
class ShopAuth:
    def ensure_state(self, *, state, driver, target):
        # 应用项目实现以下契约：
        # authenticated: 验证目标账号与会话，必要时登录，再验证。
        # anonymous: 清除/退出会话，再验证未登录。
        raise NotImplementedError("Implement the app-specific authentication flow")
```

这里是接口骨架，不是可执行的登录实现。账号来自应用项目的安全配置/租约服务。UI 登录可作为初始实现；有测试环境会话入口时可以替换，但 API 获得 token 不会自动让原生 App 登录。

业务用例声明 `@pytest.mark.auth_state("authenticated")` 并使用 prepared_app 或依赖它的页面 fixture。登录专项用例声明 anonymous，再在测试正文执行 UI 登录并断言，不能依赖另一条登录测试。

## 5. 状态准备与清理

```python
class ShopState:
    def prepare(self, *, driver, target, cleanup):
        # 修改资源前登记幂等清理；资源 ID 应按用例独占。
        cleanup.register("restore test data", self.restore)
        self.seed()

    def verify(self, *, driver, target):
        # 失败抛异常。方法正常返回代表验证通过。
        self.assert_ready(driver)
```

seed、restore、assert_ready 由具体 App 实现。fixture 返回 ShopState 对象即可接入生命周期。该接口不会自动提供后端数据管理；不要给多个 worker 使用同一个可变账号的数据。

本地全新与账号数据全新是两个条件。清理本地数据不会删除服务端收藏、订单或历史。

## 6. 弹窗与诊断

OverlayHandlers 接收名称到 `() -> bool` 回调的映射。仅识别并关闭已知可忽略弹窗，成功关闭返回 True；关闭失败抛异常。将 driver.preserved_overlays 传给 preserved 参数，支持专用弹窗测试。

在 App 的操作边界调用处理器，不能靠启动时检查一次来覆盖异步弹窗。不要默认重放下单、支付等有副作用的动作。

diagnostic_collectors 返回 `collector(evidence_path) -> JSON 可序列化对象` 函数列表，用于解析已采集证据；不要在 collector 中修改应用状态。参考 Kazumi diagnostics 实现。

## 7. 接入验收

分别验证：单独执行、任意顺序、上一条失败后执行、同平台多设备、跨平台并行、准备/清理失败。先用 fake driver 验证协议，再用真实设备验证平台行为。公开展示前把示例标识、包路径和网络前置条件写清楚。

## 页面定位器

Kazumi 示例将命名定位器放在对应 Page 类：固定入口使用类常量（如 `SettingsPage.ENTRY`），动态标签使用工厂（如 `MainPage.tab_locator(platform, label)`）。通用转义及 Android/iOS 策略生成在 `appium_testkit/pages/locators.py`。Page 负责动作、等待与业务结果验证，不缓存 WebElement。独立弹窗的定位归属对应 Component；页面复杂后再拆分专属定位器模块，避免所有页面共享一个巨大的定位器文件。

当前 Kazumi 引导通过 progress ID 读取进度状态，推荐卡片通过番剧业务 ID 定位。页面树仍用于内容断言和失败诊断。具体 ID 与原生平台映射见 [稳定语义标识](semantic-identifiers.md)。
