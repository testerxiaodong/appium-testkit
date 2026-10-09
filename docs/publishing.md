# GitHub 发布准备

当前整理的是本地可发布内容；没有创建远程仓库、提交、push 或发布 Release。

## 提交范围

提交框架、App 适配器、测试、文档、示例配置、pyproject.toml、uv.lock、Makefile 和 CI。

不提交本地 devices.yaml/apps.yaml、.env、安装包、artifacts、IDE 状态、缓存、签名文件、设备 ID 和测试账号。忽略规则不会自动删除 Git 已跟踪的文件；提交前同时检查索引和暂存 diff。

```bash
git status --short --untracked-files=all
git ls-files
git diff --cached --stat
git diff --cached
```

先审查文件列表，再暂存需要的目录。不要强制添加被忽略的配置或安装包。当前仓库尚无可供检查的已提交历史；今后曾提交过的密钥即使删除也需要单独处理历史和凭证。

## 发布前人工核对

- 从干净副本执行文档中的安装和框架质量检查；没有私有 YAML 也能完成收集。
- 配置真实设备后再跑手机用例；CI 的 collect-only 不算移动端验证。
- MIT 适用于本仓库原创内容；第三方来源在 THIRD_PARTY_NOTICES 中列明。
- 不公开复制原始报告；截图和 XML 可能含个人信息，脱敏不是完全保证。
- 演示建议录制一次：准备状态 → 更新弹窗处理 → 业务断言 → Allure 证据。
- README 不放未经验证的 CI badge、下载量或稳定性承诺。

## 仓库展示建议

名称可以继续使用 appium-testkit，无需为了显得复杂而改名。简介可使用：

> Python Appium starter for Android and iOS, with explicit state management, device isolation and failure observability.

建议 topics：appium、pytest、android、ios、test-automation、allure。

首个版本使用 0.1.x，说明接口仍可能调整。不要把本地测试通过写成云端 CI 已经通过；实际 push 后需查看工作流结果。
