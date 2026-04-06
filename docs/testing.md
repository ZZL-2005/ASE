# 测试指南

## 1. 访问 Rocket.Chat

打开浏览器访问：http://localhost:3001

## 2. 初始化设置

首次访问会进入设置向导：
1. 选择语言
2. 创建管理员账号
3. 设置组织信息

## 3. 创建 Agent 账号

登录后，创建用于测试的账号：
- 用户名: `agent`
- 邮箱: `agent@ase.local`
- 密码: `agent_pass_2026`

## 4. 创建测试频道

创建一个测试频道用于消息收发

## 5. 启动 Agent

```bash
cd /new_disk4/jiayue_pu/ZZL/ASE
python -m agent.main
```

## 6. 测试消息流

在 Rocket.Chat 中发送消息，agent 应该会回复 "Echo: [你的消息]"
