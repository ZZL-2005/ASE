# ASE 架构设计

## 1. 系统概述

ASE (Agent Safety Environment) 是一个用于研究 agent 安全性的实验框架，提供完全可控、可复现的隔离环境。

## 2. 架构分层

### 2.1 外部调度层 (Host Orchestrator)

基于 OpenSandbox 改造，负责：
- Docker 容器生命周期管理
- 多容器编排和协调
- 统一时间戳管理
- 执行轨迹采集
- 状态快照和恢复

### 2.2 容器化沙箱层

#### Agent Sandbox
- 基于 nanobot 框架改造
- 核心组件：agent loop, tool system, message bus
- 新增本地服务 channels (Rocket.Chat, Email)
- 支持 API 模式和本地 vLLM

#### User Sandbox
- 真人交互模式
- LLM 模拟用户模式

#### 本地服务
- Rocket.Chat Server - 即时通讯
- Email Server - 邮件服务
- Web Environment - 虚拟网页环境

## 3. 消息流设计

```
User → Rocket.Chat Server → Agent (RocketChatChannel)
                                ↓
                           Agent Loop (LLM + Tools)
                                ↓
Agent (RocketChatChannel) → Rocket.Chat Server → User
```

关键特性：
- 消息必须经过本地服务，不允许直连
- 支持流式消息
- 完整轨迹记录

## 4. 核心组件

### 4.1 Agent Core (from nanobot)

**Agent Loop** (`agent/core/loop.py`)
- 消息处理循环
- LLM 调用
- Tool calling 机制
- 流式响应

**Message Bus** (`agent/bus/`)
- InboundMessage / OutboundMessage
- 异步队列
- 通道解耦

**Tools** (`agent/core/tools/`)
- 文件系统操作
- Shell 命令执行
- Web 搜索和抓取
- MCP 集成

### 4.2 Channel 适配层

**BaseChannel** (`agent/channels/base.py`)
```python
class BaseChannel:
    async def start()           # 启动监听
    async def stop()            # 停止服务
    async def send(msg)         # 发送消息
    async def _handle_message() # 处理入站消息
```

**RocketChatChannel** (待实现)
- WebSocket 连接
- REST API 发送
- 消息格式转换

**EmailChannel** (待实现)
- IMAP 监听
- SMTP 发送
- 附件处理

### 4.3 Orchestrator (from OpenSandbox)

**Docker Runtime** (`orchestrator/docker.py`)
- 容器创建和销毁
- 资源配额管理
- 网络配置

**Sandbox Service** (`orchestrator/sandbox_service.py`)
- 生命周期管理
- 状态跟踪
- TTL 和续期

**Trajectory Collector** (待实现)
- 事件采集
- 时间戳对齐
- 持久化存储

**Replay Engine** (待实现)
- 快照管理
- 事件重放
- 状态恢复

## 5. 网络架构

### Docker 网络
- 自定义 bridge 网络：`ase-network`
- 容器间通过容器名通信
- 最小化端口暴露

### 端口映射
- Rocket.Chat: 3000 (开发)
- Email SMTP: 25, 587
- Email IMAP: 143, 993
- Orchestrator API: 8080

## 6. 轨迹格式

JSON Lines 格式，每行一个事件：

```json
{"timestamp": "2026-04-01T15:30:00.123Z", "type": "message.inbound", "channel": "rocketchat", "sender_id": "user1", "content": "hello"}
{"timestamp": "2026-04-01T15:30:01.456Z", "type": "tool.call", "tool": "web_search", "params": {"query": "weather"}}
{"timestamp": "2026-04-01T15:30:02.789Z", "type": "tool.result", "tool": "web_search", "result": "..."}
```

事件类型：
- `message.inbound` / `message.outbound`
- `tool.call` / `tool.result`
- `container.state_change`
- `file.operation`
- `shell.command`

## 7. 状态恢复机制

### 快照策略
- 定期自动快照（可配置间隔）
- 关键操作前手动快照
- 使用 Docker commit 或卷备份

### Replay 流程
1. 恢复到指定快照
2. 按轨迹顺序重放事件
3. 跳过不确定性操作
4. 验证状态一致性

### Rollback 流程
1. 停止所有容器
2. 恢复文件系统快照
3. 重启容器
4. 重新建立服务连接

## 8. 安全隔离

- 容器间网络隔离
- 不允许访问真实互联网
- 资源配额限制
- 最小权限原则

## 9. 可扩展性

- 支持新增 channel 类型
- 支持自定义 tool
- 支持多种 LLM 后端
- 支持 Kubernetes 部署（未来）
