# Connector Project

轻量级编排器，通过任务驱动的工作流让 Claude 与 OpenAI Codex、Google Gemini 等 AI 编程助手协作。

## 工作流程

```
Claude（编排者）               Codex / Gemini（代码生成器）
      │                                    │
      ├─ 1. 创建任务规格（JSON）              │
      ├─ 2. 通过 CLI 分发 ──────────────────►
      │                                    ├─ 3. 生成代码
      ◄────────────────────────────────────┤
      ├─ 4. 审阅并集成 ─────────────────────►
```

1. **定义任务** — 在 `tasks/` 目录下创建包含系统角色和提示词的任务规格文件
2. **分发生成** — 执行 `python main.py --run task.json` 将任务发送给指定的 AI 后端
3. **输出代码** — 后端（Codex 或 Gemini）生成的代码保存到 `workspace/`
4. **审阅集成** — Claude 对生成结果进行审阅、修改并集成

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥（复制 .env.example 为 .env，填入你的密钥）
cp .env.example .env

# 创建任务
python main.py new my_task.json "写一个按指定 key 对字典列表排序的 Python 函数"

# 查看所有任务
python main.py list

# 运行任务（默认使用 gemini）
python main.py run my_task.json

# 指定后端运行
python main.py run my_task.json --backend codex
```

## 项目结构

```
connector_project/
├── main.py                  # 编排器 CLI 入口
├── config.json              # 模型与上下文配置
├── bridge/
│   ├── claude_bridge.py     # Claude 与 AI 后端之间的 CLI 桥接
│   ├── codex_client.py      # OpenAI API 封装
│   └── gemini_client.py     # Google Gemini API 封装
├── tasks/                   # JSON 任务规格文件
│   └── example_reverse_api.json
└── workspace/               # 生成的代码输出
```

## 支持的后端

| 后端    | 模型（可配置）       | 所需密钥           |
|---------|---------------------|-------------------|
| Gemini  | `gemini-2.5-flash`  | `GEMINI_API_KEY`  |
| Codex   | `gpt-4o`            | `OPENAI_API_KEY`  |

两个后端均支持通过 `*_PROXY` 环境变量配置 HTTP 代理。

## 配置

编辑 `config.json` 可切换模型或调整上下文行为：

```json
{
  "models": {
    "codex": "gpt-4o",
    "gemini": "gemini-2.5-flash"
  },
  "context": {
    "max_history": 20,
    "save_context": true
  }
}
```

## 环境变量

| 变量              | 说明                         |
|------------------|-----------------------------|
| `OPENAI_API_KEY` | OpenAI API 密钥（Codex 后端） |
| `OPENAI_PROXY`   | OpenAI 的 HTTP 代理（可选）   |
| `GEMINI_API_KEY` | Google Gemini API 密钥       |
| `GEMINI_PROXY`   | Gemini 的 HTTP 代理（可选）   |

## 任务规格格式

```json
{
  "role": "你是一位资深软件工程师。",
  "prompt": "你希望 AI 构建的内容",
  "output_file": "result.py",
  "context_file": "session_context.json"
}
```
