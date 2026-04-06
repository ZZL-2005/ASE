# 状态恢复机制

## 设计原理

### 双向轨迹合并
1. 读取 agent 和 user 的轨迹文件
2. 按时间戳合并所有事件
3. 重放到指定步骤

## 使用方法

### 1. 加载轨迹
```python
from orchestrator.recovery import StateRecovery

recovery = StateRecovery()
trajectories = recovery.load_trajectories("20260402_001234")
```

### 2. 合并轨迹
```python
merged = recovery.merge_trajectories(trajectories)
```

### 3. 恢复到指定步骤
```python
events = recovery.replay_to_step("20260402_001234", step=10)
```

### 4. 查看状态
```python
state = recovery.get_state_at_step("20260402_001234", step=10)
print(state['summary'])
```

## 状态信息

包含：
- 消息数量
- LLM 调用次数
- Tool 调用次数
- 用户操作次数
