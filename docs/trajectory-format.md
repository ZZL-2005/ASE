"""Trajectory format specification."""

# 设计理念

## 双向轨迹记录
- **Agent 沙箱**：记录 LLM 完整输入输出、tool 调用、内部状态
- **User 沙箱**：记录用户操作（发邮件、发消息、网页操作）
- 两者共同决定环境状态，用于状态恢复

## 完整性要求
- Agent 的真实输入输出必须完整记录
- 用于可解释性分析

# Event Types

## Agent 沙箱事件
- `llm.call` - LLM 调用（完整 prompt 和 response）
- `tool.call` - Tool 调用（参数和结果）
- `message.inbound` - 接收消息
- `message.outbound` - 发送消息

## User 沙箱事件
- `user.action` - 用户操作（发邮件、发消息、网页操作）

# 示例

```json
{"timestamp": "2026-04-02T00:00:00.000Z", "sandbox": "agent", "type": "llm.call", "data": {"prompt": "...", "response": "...", "model": "claude-3"}}
{"timestamp": "2026-04-02T00:00:01.000Z", "sandbox": "user", "type": "user.action", "data": {"action_type": "send_email", "details": {...}}}
```

