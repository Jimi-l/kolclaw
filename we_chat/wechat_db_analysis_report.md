# 微信本地数据库只读探查报告

## 1. 背景与本轮目标

本轮目标是验证工作区中的微信本地数据库文件能否被直接作为 SQLite 数据源读取，并初步判断它们是否适合作为后续“按会话导出聊天记录、脱敏、场景划分、话术标签化”的自研底座。

本轮只做只读探查和文档化，不做 GUI、前端、媒体解密、图片/视频导出，也不修改任何原始 `.db`、`.db-wal`、`.db-shm` 文件。

数据目录：

```text
/home/tuo/project/we_chat/data
```

只读探查脚本：

```text
/home/tuo/project/we_chat/scripts/inspect_wechat_dbs.py
```

## 2. 数据文件概览

| 文件 | 大小 | 说明 |
| --- | ---: | --- |
| `contact.db` | 8,876,032 bytes | 联系人库主文件，当前不是标准 SQLite 明文头 |
| `contact.db-wal` | 4,194,304 bytes | SQLite WAL 文件 |
| `contact.db-shm` | 32,768 bytes | SQLite SHM 文件 |
| `session.db` | 503,808 bytes | 会话库主文件，当前不是标准 SQLite 明文头 |
| `session.db-wal` | 4,194,304 bytes | SQLite WAL 文件 |
| `session.db-shm` | 32,768 bytes | SQLite SHM 文件 |
| `message_0.db` | 8,122,368 bytes | 消息库主文件，当前不是标准 SQLite 明文头 |
| `message_0.db-wal` | 4,194,304 bytes | SQLite WAL 文件 |
| `message_0.db-shm` | 32,768 bytes | SQLite SHM 文件 |
| `message_resource.db` | 319,488 bytes | 消息资源库主文件，当前不是标准 SQLite 明文头 |
| `message_resource.db-wal` | 304,912 bytes | SQLite WAL 文件 |
| `message_resource.db-shm` | 32,768 bytes | SQLite SHM 文件 |
| `media_0.db` | 204,800 bytes | 媒体库主文件，当前不是标准 SQLite 明文头 |
| `media_0.db-wal` | 395,552 bytes | SQLite WAL 文件 |
| `media_0.db-shm` | 32,768 bytes | SQLite SHM 文件 |

五个主库文件的前 16 字节均不匹配标准 SQLite magic header：

```text
SQLite format 3\0
```

因此它们不能被当作普通明文 SQLite 文件直接读取。

## 3. 数据库可读性检查结果

探查方式：

- 使用 Python 标准库 `sqlite3`。
- 使用只读 URI：`file:<path>?mode=ro`。
- 尝试执行 `PRAGMA integrity_check`。
- 尝试读取 `sqlite_master`。
- 不执行任何写入 SQL。

| 数据库 | 文件存在 | SQLite 明文头 | 只读连接 | `integrity_check` | `sqlite_master` | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| `contact.db` | 是 | 否 | 成功建立连接句柄 | `DatabaseError: file is not a database` | `DatabaseError: file is not a database` | 不可直接读取 |
| `session.db` | 是 | 否 | 成功建立连接句柄 | `DatabaseError: file is not a database` | `DatabaseError: file is not a database` | 不可直接读取 |
| `message_0.db` | 是 | 否 | 成功建立连接句柄 | `DatabaseError: file is not a database` | `DatabaseError: file is not a database` | 不可直接读取 |
| `message_resource.db` | 是 | 否 | 成功建立连接句柄 | `DatabaseError: file is not a database` | `DatabaseError: file is not a database` | 不可直接读取 |
| `media_0.db` | 是 | 否 | 成功建立连接句柄 | `DatabaseError: file is not a database` | `DatabaseError: file is not a database` | 不可直接读取 |

说明：

- `sqlite3.connect(..., mode=ro)` 能创建连接对象，不代表数据库可读；真正读取 schema 或做完整性检查时失败。
- 失败原因一致：主库文件不是 SQLite 可识别的明文数据库格式。
- 这更像是加密后的 SQLite 数据页，或微信对主库做了非明文封装。

### WAL/SHM 状态

`file` 工具能识别 5 组 WAL/SHM 文件为 SQLite WAL/SHM 形态。WAL header 显示 page size 为 `4096`，估算 frame 数如下：

| WAL 文件 | 大小 | page size | 估算 frame 数 |
| --- | ---: | ---: | ---: |
| `contact.db-wal` | 4,194,304 bytes | 4096 | 1018 |
| `session.db-wal` | 4,194,304 bytes | 4096 | 1018 |
| `message_0.db-wal` | 4,194,304 bytes | 4096 | 1018 |
| `message_resource.db-wal` | 304,912 bytes | 4096 | 74 |
| `media_0.db-wal` | 395,552 bytes | 4096 | 96 |

但是主库不可读时，SQLite 不能可靠通过 WAL 补出 schema。当前不能判断 WAL 是否包含完整未 checkpoint 状态，也不能从 WAL 安全抽取表结构。

## 4. `contact.db` 分析

### 可读性

- 文件存在：是。
- 主库大小：8,876,032 bytes。
- SQLite 明文头：否。
- 只读连接：连接句柄可创建。
- schema 读取：失败，`DatabaseError: file is not a database`。

### 表结构与对象

当前无法读取：

- 表名。
- 索引名。
- 视图名。
- 触发器。
- 每张表字段名、字段类型、主键。
- FTS/虚拟表/技术表。

### 语义判断

由于没有可读 schema 和样例数据，以下字段暂不可判断：

- wxid / 微信号。
- 昵称 / 备注名。
- 联系人类型。
- 群聊标记。
- 企业联系人。
- 标签。
- 状态。
- 头像相关字段。

联系人主表、搜索索引表、缓存表、扩展表也暂不可分类。后续拿到明文库后，应优先寻找字段名或样例值中包含 `wxid`、`userName`、`nickname`、`remark`、`alias`、`avatar`、`label`、`type`、`verify`、`chatroom`、`corp` 等语义的表。

## 5. `session.db` 分析

### 可读性

- 文件存在：是。
- 主库大小：503,808 bytes。
- SQLite 明文头：否。
- 只读连接：连接句柄可创建。
- schema 读取：失败，`DatabaseError: file is not a database`。

### 表结构与对象

当前无法读取表、索引、视图、触发器、字段和样例数据。

### 语义判断

由于没有可读 schema，以下字段暂不可判断：

- session_id。
- talker / 会话对象。
- 会话类型。
- 最后一条消息。
- 未读数。
- 排序时间。
- 会话状态。
- 同步、增量、技术辅助字段。

后续拿到明文库后，`session.db` 应优先验证是否存在会话主表，因为它通常是“选择某个会话并导出”的入口。

## 6. `message_0.db` 分析

### 可读性

- 文件存在：是。
- 主库大小：8,122,368 bytes。
- SQLite 明文头：否。
- 只读连接：连接句柄可创建。
- schema 读取：失败，`DatabaseError: file is not a database`。

### 表结构与对象

当前无法读取表、索引、视图、触发器、字段和样例数据。

### 语义判断

由于没有可读 schema，以下字段暂不可判断：

- message_id。
- session_id / talker。
- sender。
- create_time。
- msg_type。
- content。
- status。
- is_send。
- 资源引用字段。

从产品目标看，`message_0.db` 很可能是第一版“单会话纯文本导出”的核心数据源，但当前文件不能直接读取，尚无法验证是否按会话分表、是否按 `talker` 过滤、文本消息类型如何编码、时间戳单位是什么。

## 7. `message_resource.db` 分析

### 可读性

- 文件存在：是。
- 主库大小：319,488 bytes。
- SQLite 明文头：否。
- 只读连接：连接句柄可创建。
- schema 读取：失败，`DatabaseError: file is not a database`。

### 表结构与对象

当前无法读取表、索引、视图、触发器、字段和样例数据。

### 语义判断

由于没有可读 schema，以下内容暂不可判断：

- 是否存在消息 ID 到资源 ID 的映射。
- 是否存在图片、视频、语音、文件等资源类型字段。
- 是否存在本地路径、资源 key、下载状态字段。

第一版纯文本导出可以先不依赖该库。等文本导出链路跑通后，再把它作为图片、视频、语音、文件导出的扩展数据源验证。

## 8. `media_0.db` 分析

### 可读性

- 文件存在：是。
- 主库大小：204,800 bytes。
- SQLite 明文头：否。
- 只读连接：连接句柄可创建。
- schema 读取：失败，`DatabaseError: file is not a database`。

### 表结构与对象

当前无法读取表、索引、视图、触发器、字段和样例数据。

### 语义判断

由于没有可读 schema，以下内容暂不可判断：

- 媒体对象主表。
- 本地路径。
- 资源 key。
- 媒体类型。
- 缩略图、原图、高图、视频字段。
- 与 `message_resource.db` 的关联键。

第一版纯文本导出建议暂不接入 `media_0.db`。

## 9. 五个数据库之间的关系推测

以下是产品链路层面的推测，不是基于当前 schema 的已验证结论：

- `session.db`：可能负责会话列表，是用户选择导出哪个会话的入口。
- `message_0.db`：可能负责消息明细，是按会话导出聊天内容的核心数据源。
- `contact.db`：可能负责联系人元数据，用来把 wxid/talker 映射为昵称、备注名、群聊名等可读展示名。
- `message_resource.db`：可能负责消息到资源的映射，例如图片、文件、视频、语音。
- `media_0.db`：可能负责媒体对象详情，例如本地路径、缩略图、原图、视频资源信息。

第一版理论链路应是：

```text
session.db 选择会话
  -> message_0.db 按会话读取文本消息
  -> contact.db 补充联系人展示名
  -> 导出纯文本/Markdown/JSON
```

资源链路应后置：

```text
message_0.db 消息资源引用
  -> message_resource.db 资源映射
  -> media_0.db 媒体对象/路径
```

当前无法验证 join key，不能确定是 `session_id`、`talker`、`wxid`、`msg_id`、`local_id` 还是其他字段。

## 10. 目前最适合作为第一版导出链路的数据源

在获得可读明文 SQLite 之前，当前这批 `.db` 文件不适合作为直接读取底座。

SQLite 路线仍然值得继续，因为：

- 文件体系呈现出典型 SQLite + WAL/SHM 形态。
- 数据分库名称清晰，符合联系人、会话、消息、资源、媒体的职责拆分。
- 如果能获得明文库或正确解密流程，后续可以用标准 SQLite 工具链探查和读取。

第一版最小可行导出链路应优先基于：

1. `session.db`：列出会话，定位目标会话。
2. `message_0.db`：按会话读取消息，筛选文本消息，按时间排序。
3. `contact.db`：补充会话名、联系人备注名、昵称等展示信息。

`message_resource.db` 和 `media_0.db` 暂不进入第一版 MVP。

## 11. 风险与不确定点

- 加密方式未知：当前主库不是明文 SQLite，必须先确认微信版本对应的数据库加密方式和密钥来源。
- WAL 完整性未知：虽然 WAL/SHM 存在，但主库不可读时不能判断 checkpoint 状态和完整性。
- 字段语义未知：未能读取 schema 前，不能确认表结构、字段名、字段类型和主键。
- 微信版本差异：不同客户端版本可能改变库名、表名、字段名或分库策略。
- 多库关联键未知：会话、联系人、消息之间的关联字段需要在明文库中验证。
- 时间戳单位未知：需要验证是秒、毫秒、微秒，还是微信内部时间基准。
- 敏感数据处理：后续样例输出必须继续做 wxid、昵称、备注、正文、路径、URL 等字段遮罩。

## 12. 下一步开发 plan

### 12.1 第一版“单会话纯文本导出”应基于哪些表实现

拿到可读明文库后，优先在三个库里寻找主表：

- `session.db`：会话主表，负责列出会话和排序。
- `message_0.db`：消息主表，负责按会话读取消息。
- `contact.db`：联系人主表，负责把会话对象或发送方映射成人类可读名称。

资源库暂不参与第一版纯文本导出。

### 12.2 contact / session / message 建议如何关联

待明文 schema 可读后，按以下顺序验证：

1. 在 `session.db` 中找会话对象字段，重点看是否有 `session_id`、`talker`、`username`、`wxid`、`chatroom` 等字段。
2. 在 `message_0.db` 中找同名或同语义字段，验证消息是否能按会话对象过滤。
3. 在 `contact.db` 中找联系人唯一标识字段，验证能否用 `talker/wxid/username` 补充昵称或备注名。
4. 对同一会话抽样比对最后一条消息时间和内容摘要，确认 `session.db` 与 `message_0.db` 的关联可靠。

### 12.3 下一步应优先验证什么

优先级建议：

1. 解密或获取明文 SQLite：这是后续所有 schema 探查的前置条件。
2. 消息到会话映射：确认单会话导出是否可行。
3. 文本消息类型识别：确认哪些 `msg_type` 是纯文本，哪些应跳过。
4. 时间戳解析：确认排序和导出时间格式。
5. 会话到联系人映射：补充会话名、备注名、昵称。

### 12.4 第一版最小可行功能建议

第一版只做命令行只读导出：

- 列出最近会话：显示脱敏后的会话标识、展示名、最后消息时间。
- 选择一个会话：通过会话标识或序号指定。
- 导出文本消息：按时间升序输出发送方、时间、文本正文。
- 输出格式：优先 Markdown 或 JSONL。
- 默认脱敏：wxid、昵称、备注、URL、手机号、邮箱等敏感内容做遮罩。

### 12.5 明确建议暂时不要做

- 不做 GUI 或前端页面。
- 不做图片、视频、语音、文件导出。
- 不做媒体解密。
- 不做自动写回数据库。
- 不做大规模话术标签化。
- 不做完整产品化封装。
- 不在 schema 未验证前硬编码字段名。

## 附：当前脚本验证命令

```bash
python3 /home/tuo/project/we_chat/scripts/inspect_wechat_dbs.py
```

当前输出要点：

- 5 个 `.db` 文件均显示 `sqlite_magic: False`。
- 5 个 `.db` 文件均显示 `connect_mode_ro: ok`。
- 5 个 `.db` 文件读取 `PRAGMA integrity_check` 均失败：`DatabaseError: file is not a database`。
- 5 个 `.db` 文件读取 `sqlite_master` 均失败：`DatabaseError: file is not a database`。
- 5 个 `.db` 文件 `object_count: 0`，不是因为库为空，而是因为 schema 无法读取。
