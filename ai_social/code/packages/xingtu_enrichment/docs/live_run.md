# 星图实时流程运行说明

## 目标

这一轮的目标不是做复杂的 brief 规划，而是先让星图实时流程最小可用：

1. 读取已登录的 Playwright storage state
2. 打开星图
3. 进入 `找达人`
4. 应用一小组筛选条件
5. 打开至少一个达人详情页
6. 提取结构化达人信息
7. 通过脚本或最小测试完成验证

## 相关代码位置

- `apps/api/app/services/xingtu_workflow.py`
  星图页面工作流本体

- `apps/api/app/services/xingtu_runner.py`
  带认证上下文的实时执行入口

- `apps/api/run_xingtu_flow.py`
  可直接运行的 CLI 示例脚本

- `apps/api/app/schemas/xingtu.py`
  筛选配置、结果行、详情页和实时运行结果的结构化模型

- `apps/api/tests/test_xingtu_live_flow.py`
  不依赖浏览器的纯 Python 单元测试

## 如何提供 storage state

当前支持三种方式：

### 方式一：命令行参数

```bash
cd /home/tuo/project/ai_social/code/apps/api
/home/tuo/project/ai_social/code/.venv/bin/python run_xingtu_flow.py \
  --storage-state /home/tuo/project/ai_social/playwright/.auth/xingtu.json \
  --filters-json '{"named_filters":{"美妆":["美妆测评种草"]}}'
```

### 方式二：环境变量

```bash
cd /home/tuo/project/ai_social/code/apps/api
export XINGTU_STORAGE_STATE=/home/tuo/project/ai_social/playwright/.auth/xingtu.json
export XINGTU_FILTERS_JSON='{"named_filters":{"美妆":["美妆测评种草"]}}'
/home/tuo/project/ai_social/code/.venv/bin/python run_xingtu_flow.py
```

### 方式三：JSON 配置文件

配置文件示例：

```json
{
  "storage_state_path": "/home/tuo/project/ai_social/playwright/.auth/xingtu.json",
  "account_name": "Demo Workspace Account 001",
  "headless": false,
  "row_limit": 3,
  "target_row_index": 0,
  "filter_config": {
    "named_filters": {
      "美妆": ["美妆测评种草"]
    }
  }
}
```

运行方式：

```bash
cd /home/tuo/project/ai_social/code/apps/api
/home/tuo/project/ai_social/code/.venv/bin/python run_xingtu_flow.py --config /path/to/xingtu_live_config.json
```

## 运行前准备

当前建议直接使用统一工作区 `code/.venv` 下的项目虚拟环境：

```bash
cd /home/tuo/project/ai_social/code
/home/tuo/project/ai_social/code/.venv/bin/python -m pip install -r apps/api/requirements.txt playwright
/home/tuo/project/ai_social/code/.venv/bin/python -m playwright install chromium
```

说明：

- `xingtu_workflow.py` 仍然保持“接收已认证 Page”的边界，不在工作流内部写死 storage state。
- `run_xingtu_flow.py` 和 `xingtu_runner.py` 才负责浏览器启动与 storage state 注入。
- 路径统一由 `app/core/config.py` 推导。默认情况下，如果工作区下存在 `playwright/.auth/xingtu.json`，CLI 可以直接解析到它。

## 最小实时 smoke 路径

推荐先用一个最小筛选跑通整条链路：

```bash
cd /home/tuo/project/ai_social/code/apps/api
/home/tuo/project/ai_social/code/.venv/bin/python run_xingtu_flow.py \
  --storage-state /home/tuo/project/ai_social/playwright/.auth/xingtu.json \
  --account-name 'Demo Workspace Account 001' \
  --filters-json '{"named_filters":{"美妆":["美妆测评种草"]}}' \
  --row-limit 3 \
  --row-index 0 \
  --headed
```

成功时，脚本会输出 JSON，包含：

- 首页 URL
- `找达人` 页 URL
- 收集到的结果行数量
- 被打开的目标结果行
- 结构化达人详情
- 缺失关键字段列表

## 如何运行纯 Python 单元测试

这些测试不访问星图页面，主要覆盖：

- 录制中已识别的关键指标文本解析
- 详情字段校验
- 实时运行配置模型

运行方式：

```bash
cd /home/tuo/project/ai_social/code
/home/tuo/project/ai_social/code/.venv/bin/python -m unittest discover -s apps/api/tests -v
cd /home/tuo/project/ai_social
/home/tuo/project/ai_social/code/.venv/bin/python -m unittest discover -s tests -v
```

## 当前已支持的最小筛选输入

这一轮只支持轻量结构化筛选，不做复杂自然语言规划。

当前最实用的输入是：

```json
{
  "named_filters": {
    "美妆": ["美妆测评种草"]
  }
}
```

也可以继续扩展为：

```json
{
  "named_filters": {
    "美妆": ["美妆测评种草"],
    "家居家装": ["全选"]
  }
}
```

其中 `named_filters` 反映的是页面上真实存在的“筛选组 -> 下拉项”模式。

## 当前最容易受真实 DOM 影响的点

- 首页账号卡片入口仍然依赖文本匹配，若账号卡 DOM 变化，需要继续收紧选择器。
- `找达人` 导航目前主要依赖 role + 文本。
- 某些筛选器是下拉菜单，菜单容器 ID 可能是动态的。
- 结果区既可能是表格，也可能是卡片列表，因此目前做了双通道兼容。
- 详情页指标有一部分可以走结构化卡片读取，另一部分仍需回退到整页文本解析。
- 达人详情有时会新开弹窗页，有时可能是同页跳转，当前 runner 已兼容这两种情况。

## 本轮实际验证结果

已在当前 WSL 工作区完成一次真实在线 smoke：

- 成功读取 `storage state`
- 成功进入星图首页并点击工作台账号入口
- 成功进入 `找达人`
- 成功应用最小筛选并收集结果行
- 成功打开至少一个达人详情页
- 成功提取结构化达人信息并输出 JSON

当前已知不稳定点：

- 首页账号入口仍然依赖文本和最小可见块启发式，DOM 变动时可能失效
- 下拉筛选项目前可以工作，但精确命中仍依赖真实菜单结构
- 结果列表当前优先走 `.author-nickname` / `.author-name`，如果列表 DOM 改版需要继续收紧
- 详情页仍有部分字段走整页文本回退解析，因此字段覆盖率依赖页面文案稳定性
