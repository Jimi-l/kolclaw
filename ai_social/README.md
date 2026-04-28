# ai_social

**Project Status:** `canonical`

`ai_social` 是当前主产品壳目录，承担 brief 解析、shortlist demo、星图截图抽取和 CPM 估算这条面向业务使用的主链路。

实际可运行代码在 [code/README.md](./code/README.md)。

目录约定：

- `code/`：主实现目录，含 `apps/api`、`apps/web`、模块 docs 与示例
- `external_docs/`：外部参考资料
- `playwright/`：本地浏览器登录态与自动化辅助目录，不应提交真实 auth 文件
- `tests/`：项目级测试或试验脚本
- `tmp/`：临时调试目录
