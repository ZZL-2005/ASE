# ASE - Agent Safety Environment

Agent Safety Environment (ASE) 是一个用于研究 agent 行为、安全性、可复现性与可解释性的实验框架。

## 核心特性

- **实验环境可复现** - 所有组件版本固定，状态可追溯
- **组件运行隔离** - 基于 Docker 容器的沙箱环境
- **多主体交互** - 支持 agent 与模拟用户的交互
- **执行轨迹记录** - 完整记录所有操作和状态变化
- **状态恢复机制** - 基于轨迹的 replay 和 rollback
- **本地闭环环境** - 不接入真实互联网，所有服务本地部署

## 架构概览

```
外部调度层 (Orchestrator)
    ├── Agent Sandbox (基于 nanobot)
    ├── User Sandbox
    ├── Rocket.Chat Server
    ├── Email Server
    └── Web Environment
```

## 项目结构

```
ASE/
├── agent/              # Agent 沙箱
│   ├── core/           # agent loop, tools (from nanobot)
│   ├── bus/            # message bus (from nanobot)
│   └── channels/       # 本地服务 channels
├── user/               # User 沙箱
├── services/           # 本地服务配置
│   ├── rocketchat/     # Rocket.Chat
│   ├── email/          # Email server
│   └── web/            # Web environment
├── orchestrator/       # 外部调度器 (基于 OpenSandbox)
├── scripts/            # CLI 工具和辅助脚本
├── tasks/              # Task 运行数据 (轨迹、compose 文件)
├── docs/               # 文档
└── tests/              # 测试
```

## 前置要求

- Python 3.11+
- Docker & Docker Compose
- pip 依赖：

```bash
uv pip install pyyaml loguru httpx
```

## 快速开始

所有操作通过 `scripts/ase_task.py` 完成。一个 Task 代表一次完整的实验运行，包含独立的容器集群、端口、轨迹数据。

### 1. 创建 Task

```bash
python scripts/ase_task.py create --name "my-experiment" --mode interactive
```

```bash
python scripts/ase_task.py create \
  --name "vllm-exp-001" \
  --mode interactive \
  --api-base "http://183.174.228.138:8000/v1" \
  --model "Qwen/Qwen3.5-27B"
```
输出：
```
Created: task-001
  RC port: 10001
  Web port: 10080

To start: python scripts/ase_task.py start task-001
```

`--mode` 可选：
- `interactive` — 人类通过 Rocket.Chat Web UI 与 agent 交互
- `simulated` — LLM 模拟用户自动发送消息

### 2. 启动 Task (目前启动居然要花费6-7min，是比较久的感觉。)

```bash
python scripts/ase_task.py start task-001
```

这会自动：
1. 生成该 Task 专属的 `docker-compose.yml`
2. 拉起 MongoDB、Rocket.Chat、Email Server、Web Env、Agent 共 5 个容器
3. 等待 Rocket.Chat 就绪
4. 创建 RC 账号（agent / testuser）和邮箱账号
5. Agent 自动连接 RC (WebSocket) 和 Email (IMAP)，开始监听消息

### 3. 与 Agent 交互

打开浏览器访问 `http://localhost:<RC_PORT>`（如 `http://localhost:10001`），用以下账号登录：

```
用户名: testuser
密码:   test_pass_2026
```

找到 `agent` 用户发私信，agent 会调用 LLM 自动回复。**所有 LLM 调用和工具调用会被自动记录到轨迹文件中。**

### 4. 停止 Task

```bash
python scripts/ase_task.py stop task-001
```

停止后：
- 所有容器被 `docker compose down`
- Task 状态变为 `stopped`
- **轨迹文件自动保留**在 `tasks/task-001/trajectories/agent/` 目录下

### 5. 查看轨迹

```bash
python scripts/ase_task.py trajectories task-001
```

输出示例：
```
Trajectories for task-001:

  agent:
    agent_20260402_081409.jsonl (3 events, 1552 bytes)

  user:
    (none)
```

### 6. 重放轨迹到指定步

```bash
# 重放全部事件
python scripts/ase_task.py replay task-001

# 只重放前 2 步
python scripts/ase_task.py replay task-001 --step 2
```

输出示例：
```
Trajectory replay for task-001
Total events: 3, replaying to step: 2
----------------------------------------------------------------------
  [1] 2026-04-02T08:14:37 | agent.llm.call
       model=DeepSeek-V3 (in=1908, out=3)
       prompt: ...'What is 3 times 7? Answer with just the number.'
       response: '21'

  [2] 2026-04-02T08:15:33 | agent.llm.call
       model=DeepSeek-V3 (in=1928, out=3)
       prompt: ...'What is the largest planet? One word.'
       response: 'Jupiter'

----------------------------------------------------------------------
State at step 2:
  LLM calls:     2
  Tool calls:    0
  Messages:      0
  User actions:  0
```

## CLI 命令速查

| 命令 | 说明 |
|------|------|
| `create --name NAME --mode MODE` | 创建 Task（不启动） |
| `start TASK_ID` | 启动 Task，拉起所有容器 |
| `run --name NAME` | 创建并立即启动（create + start） |
| `stop TASK_ID` | 停止 Task，保留轨迹数据 |
| `destroy TASK_ID` | 停止并删除所有数据和 volumes |
| `list` | 列出所有 Task |
| `status TASK_ID` | 查看 Task 详情和容器状态 |
| `logs TASK_ID [SERVICE]` | 查看容器日志 |
| `trajectories TASK_ID` | 列出轨迹文件 |
| `replay TASK_ID [--step N]` | 重放轨迹到第 N 步 |
| `stop-all` | 停止所有运行中的 Task |

所有命令的前缀: `python scripts/ase_task.py`

## 轨迹数据说明

### 存储位置

```
tasks/{task_id}/trajectories/
├── agent/          # Agent 侧轨迹
│   └── agent_{timestamp}.jsonl
└── user/           # User 侧轨迹 (simulated 模式)
    └── user_{timestamp}.jsonl
```

### 轨迹格式 (JSONL)

每行一个 JSON 事件：

```json
{
  "timestamp": "2026-04-02T08:14:37.133596",
  "sandbox": "agent",
  "type": "llm.call",
  "data": {
    "prompt": "What is 3 times 7?",
    "response": "21",
    "model": "DeepSeek-V3",
    "metadata": {
      "iteration": 0,
      "usage": {"prompt_tokens": 1908, "completion_tokens": 3},
      "stop_reason": "completed"
    }
  }
}
```

事件类型：
- `llm.call` — LLM 调用（含完整 prompt/response/token 统计）
- `tool.call` — 工具调用（含参数和返回值）
- `user.action` — 用户操作（发消息、发邮件）
- `message.inbound` / `message.outbound` — 消息收发

### 轨迹生命周期

- **自动写入** — Agent 每处理一条消息后自动保存轨迹
- **stop 后保留** — `stop` 只停容器，轨迹文件不受影响
- **destroy 才清理** — `destroy` 会删除容器 + volumes，但轨迹在宿主机 `tasks/` 目录仍保留
- **重放不需要容器** — `replay` 直接读取 JSONL 文件，不需要启动任何服务

## 端口分配

每个 Task 自动分配独立端口段，多个 Task 可并行运行：

```
Task N 的 base_port = 10000 + N * 100

rocketchat:  base + 1     (如 10001, 10101, 10201...)
web:         base + 80    (如 10080, 10180, 10280...)
imap:        base + 43    (如 10043, 10143, 10243...)
smtp:        base + 25
smtp_submit: base + 87
imaps:       base + 93
```

## 文档

- [架构设计](docs/architecture.md)
- [轨迹格式规范](docs/trajectory-format.md)
- [状态恢复机制](docs/recovery.md)

## 技术栈

- Python 3.11+
- Docker & Docker Compose
- nanobot (Agent 核心)
- Rocket.Chat 5.3
- docker-mailserver 13.3.1
- DeepSeek-V3 / OpenAI-compatible LLM API

## 许可证

MIT
