# search_agent

**Project Status:** `canonical`

`search_agent` 是当前达人发现与星图补数链路的运行时主实现，重点覆盖：

- `search_agent/adapters/douyin/`：抖音巡号、视频分析、链接与上传链路
- `search_agent/adapters/xingtu/`：星图搜索、页面抽取与补数 workflow
- `search_agent/tagging/`：达人标签、taxonomy、匹配逻辑
- `search_agent/models`、`utils`、`storage`：共享 schema、工具与产物写入层

## Quick Start

```bash
cd /home/tuo/project/search_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

## Runtime Data

- `runtime/` 当前同时包含真实业务输出和浏览器会话相关文件
- `runtime/browser_state/`、`local_only/env/search_agent.env`、任何 storage state / cookie / session 文件都不应提交
- 若要把某次产出纳入私有仓库，请先把可提交结果从 `runtime/` 中人工分离出来
