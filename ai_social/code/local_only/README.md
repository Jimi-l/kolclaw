# local_only

这个目录用于保存仅本地可用、不能进入 GitHub 的内容：

- `env/`：真实 API key、本地环境变量、token、cookie、storage state 路径等 secret

目录内容默认应被 `.gitignore` 忽略。

真实但不含 secret 的运行产物已经迁移到：

- `runtime/debug_runs/`
- `runtime/debug_assets/`
