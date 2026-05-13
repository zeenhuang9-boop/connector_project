# Connector Project

本地多 AI 通信中心——让 Claude、Gemini、OpenAI Codex 及其他 AI 模型能够相互实时交流。所有消息路由均为进程内处理，除各 AI 服务的 API 调用外，数据不会离开你的本机。

## 通信模式

| 模式 | 说明 |
|---------|-------------|
| **direct** | 两个 AI 之间一对一消息传递 |
| **broadcast** | 一个 AI 同时向所有其他 AI 发送消息 |
| **chain** | 顺序流水线（A → B → C → D），每个回应作为下个 AI 的输入 |
| **round_robin** | 多轮讨论，AI 轮流在彼此想法的基础上构建 |
| **moderated** | 审核 AI 先审阅消息再转给其他参与者 |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 API 密钥
cp .env.example .env    # 然后编辑 .env，填入真实密钥

# 启动交互式 REPL
python main.py interactive

# 一次性命令
python main.py ask gemini "写一个 Python 排序函数"
python main.py chain gemini codex "设计并审查一个 REST API"
python main.py roundtable "认证架构设计" gemini codex --rounds 3
python main.py broadcast "审查这段代码：..."
```

### REPL 命令

```
> ask gemini "写一个排序函数"
> broadcast "审查这个架构"
> chain gemini codex "设计然后审查"
> roundtable gemini codex "认证设计" --rounds 3
> moderated gemini codex "数据库架构设计"
> thread list
> thread show <id>
> agents
> help
> quit
```

## 项目结构

```
connector_project/
├── main.py                  # CLI 入口
├── config.json              # Agent 与安全配置
├── ai_hub/
│   ├── hub.py               # AIHub 编排器 + REPL/CLI
│   ├── message.py           # Message 数据类 + MessageBus 路由器
│   ├── adapters.py          # AIAdapter + GeminiAdapter + CodexAdapter
│   ├── conversation.py      # Thread + ConversationManager
│   └── security.py          # TokenBucket + SecurityGuard
├── bridge/
│   ├── gemini_client.py     # Google Gemini API 封装
│   └── codex_client.py      # OpenAI API 封装
├── .claude/skills/
│   └── ai-connect.md        # Claude Code skill 定义
├── .env.example             # 环境变量模板
└── requirements.txt
```

## Claude Code Skill

在 Claude Code 中输入 `/ai-connect` 即可启动多 AI REPL。Claude 作为编排者，将任务分派给其他 AI 并主持讨论。

## 配置

编辑 `config.json` 来添加 agent 或调整安全设置：

```json
{
  "agents": {
    "gemini": { "backend": "gemini", "role": "coder", "rate_limit": 1.0 },
    "codex": { "backend": "codex", "role": "reviewer", "rate_limit": 1.0 }
  },
  "security": {
    "max_message_length": 8000,
    "rate_limit_per_second": 1.0,
    "banned_patterns": ["</?system>", "ignore previous instructions"]
  },
  "context": {
    "max_history": 20,
    "save_context": true
  }
}
```

### Agent 角色

| 角色 | 说明 |
|------|-------------|
| `coder` | 编写生产级代码 |
| `reviewer` | 发现 bug 并提出改进建议 |
| `architect` | 设计系统并选择模式 |
| `critic` | 识别弱点，提出具体改进方案 |
| `moderator` | 综合多方观点，引导达成共识 |

## 支持的后端

| 后端 | 默认模型 | 所需密钥 |
|---------|--------------|--------------|
| Gemini | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| Codex | `gpt-4o` | `OPENAI_API_KEY` |

两个后端均支持通过 `GEMINI_PROXY` / `OPENAI_PROXY` 环境变量配置 HTTP 代理。

## 环境变量

| 变量 | 说明 |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API 密钥 |
| `GEMINI_PROXY` | Gemini 的 HTTP 代理（可选） |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `OPENAI_PROXY` | OpenAI 的 HTTP 代理（可选） |

## 安全

- API 密钥仅存储在 `.env` 中，绝不会出现在代码、配置或 git 中
- 消息内容自动净化——所有输出中的 API 密钥模式会被自动遮蔽
- 双层速率限制（hub 级别 + 各 agent 级别）
- 注入检测阻止系统提示词篡改
- 所有路由均为进程内处理——agent 之间不使用网络套接字
