# Media Annotation Workbench

**Project Status:** `downstream app`

面向 `AI媒介Agent` 的独立内部工作台。

这个项目围绕两条主链路搭建：

- `知识数据库`：导入 `media_knowledge_factory` 产出的快照，按用途和按文件浏览 9 份核心资产。
- `审核标注台`：围绕 `gold_episode_review_queue` 做任务领取、草稿保存、提交审核、管理员通过/退回。

## 结构

```text
media_annotation_workbench/
├── apps
│   ├── api
│   │   ├── app
│   │   ├── main.py
│   │   └── tests
│   └── web
│       ├── src
│       ├── package.json
│       └── vite.config.ts
└── docker-compose.yml
```

## 后端

### 技术栈

- FastAPI
- SQLAlchemy
- Postgres 兼容 schema
- 本地账号体系：`admin` / `annotator` / `viewer`

### 启动

```bash
cd /home/tuo/project/media_annotation_workbench/apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

默认期望的数据库连接：

`postgresql+psycopg://media_workbench:media_workbench@127.0.0.1:5432/media_annotation_workbench`

可通过环境变量覆盖：

`WORKBENCH_DATABASE_URL`

## 前端

### 技术栈

- React
- Vite
- TypeScript

### 启动

```bash
cd /home/tuo/project/media_annotation_workbench/apps/web
npm install
npm run dev
```

默认前端地址：

`http://127.0.0.1:5173`

默认代理后端：

`http://127.0.0.1:8000`

## 默认账号

- `admin / admin123`
- `annotator / annotator123`
- `viewer / viewer123`

## 数据导入

V1 不改上游工厂输出方式。

继续由 `media_knowledge_factory` 产出快照目录，例如：

`/home/tuo/project/media_knowledge_factory/outputs/seed_v1`

然后由工作台通过 `POST /api/imports` 或 Dashboard 导入这个目录，写入数据库并生成一个新的 `snapshot`。

## 审核覆盖层

系统不会直接回写原始 JSONL/YAML/Markdown 产物。

- 原始快照记录不可变
- 人工修订写入数据库的 `episode_review_edits`
- `reviewed view` 会把人工修订覆盖到 `negotiation_episodes_raw`
- 导出接口会输出带人工修订结果的 episode 视图

## 测试

```bash
cd /home/tuo/project
pytest media_annotation_workbench/apps/api/tests/test_workbench_api.py
```
