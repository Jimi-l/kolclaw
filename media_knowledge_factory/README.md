# Media Knowledge Factory

**Project Status:** `canonical`

面向 `AI媒介Agent` 的前期支持工程。

这个目录不复用 `contact_db` 或 `ai_social` 的既有处理链路，而是直接围绕业务目标提供一套独立的：

- 会话标准化
- brief 结构化抽取
- 谈判 episode 切分
- 话术模板沉淀
- 履约 / 返点 SOP 规则卡
- embedding / 检索切片导出

当前默认输入是已清洗的 WeFlow 会话目录：

`/home/tuo/project/contact_db/outputs/file_transfer_assistant_cleaned/reconstructed_weflow`

## 输出资产

运行后会生成：

- `conversation_messages.jsonl`
- `brief_cards.jsonl`
- `negotiation_episodes.jsonl`
- `talk_templates.jsonl`
- `workflow_playbook.jsonl`
- `retrieval_chunks.jsonl`
- `gold_episode_review_queue.jsonl`
- `tag_dictionary.yaml`
- `annotation_guideline.md`
- `asset_field_guide.md`

## 运行

```bash
cd /home/tuo/project
python media_knowledge_factory/scripts/run_factory.py
```

默认输出目录：

`/home/tuo/project/media_knowledge_factory/outputs/seed_v1`

## 测试

```bash
cd /home/tuo/project
pytest media_knowledge_factory/tests/test_pipeline.py
```
