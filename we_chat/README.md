# we_chat

**Project Status:** `canonical`

`we_chat` 用于保留微信本地数据库样本、只读探查脚本和路线分析文档，是 `contact_knowledge` 模块的数据入口与技术判断支撑目录。

当前重点内容：

- `data/`：原始微信本地数据库与 WAL / SHM 文件
- `scripts/inspect_wechat_dbs.py`：只读探查脚本，不写入原始 DB
- `wechat_db_analysis_report*.md`：数据库格式与可读性分析
- `wechat_routes_comparison_for_agents.md`：后续导出路线对比

## Quick Start

```bash
cd /home/tuo/project/we_chat
python3 scripts/inspect_wechat_dbs.py --data-dir /home/tuo/project/we_chat/data --sample-rows 3
```
