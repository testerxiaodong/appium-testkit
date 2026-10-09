# 贡献指南

## 开发环境

```bash
uv sync --locked
make quality
```

Python 依赖由 pyproject.toml 和 uv.lock 管理；修改依赖时同步锁文件。Appium 服务端、驱动和设备环境独立配置，不能仅靠 uv sync 完成。

## 修改约定

- 通用机制放 appium_testkit；应用定位器、登录和业务规则放 apps/<name>。
- 页面动作等待可验证的结果；不使用固定 sleep 掩盖就绪条件问题。
- 新增失败处理需要验证原始异常不被清理/采集异常覆盖。
- 平台差异明确注明支持范围，不把 simulator 通过视为真机通过。
- 更新公共 fixture / marker 时同步 docs/configuration.md 和 docs/app-state.md。
- 不复制第三方应用源码或二进制进仓库。

## 提交验证

框架改动执行 make quality；设备行为改动在适用平台执行相关移动测试，记录首次失败和复测。文档改动检查相对链接、命令与实现的一致性。

PR 描述包括问题、改动、验证命令/结果、已知限制。真实环境失败不改成 skip；只对明确不适用的前置条件或平台进行跳过。

不要上传未脱敏的设备配置、账号、日志或截图。
