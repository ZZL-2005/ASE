# CLAUDE.md
！！！！注意，不要清理其他用户的进程或者端口占用，请牢记这一点，加入到你的要求中  ！！！！
项目应该根据/new_disk4/jiayue_pu/ZZL/ASE/NEEDTEST.md文档实现详细测试。
## 1. 项目目标

我们要构建一个 **Agent Safety 研究型实验框架（ASE, Agent Safety Environment）**，用于研究 agent 在受控环境中的行为、安全性、可复现性与可解释性。

该框架必须满足以下核心要求：

- **实验环境可复现**
- **各组件运行隔离**
- **支持多主体交互**
- **支持完整执行轨迹记录**
- **支持基于轨迹的状态恢复 / replay**
- **agent 的外部操作不得直接接入真实互联网，而应尽可能在本地受控环境中完成**

---

## 2. 总体架构

系统由两层组成：

### 2.1 容器化实验环境层（Docker Sandbox Cluster）

我们将使用多个 Docker 沙箱容器来模拟完整实验环境。目标组件包括：

1. **agent 沙箱**
   - 基于 `nanobot` 框架改造
   - 负责承载 agent scaffold、tool calling、多通道消息处理等逻辑
   - 支持 API 模式模型接入
   - 也支持本地部署 `vLLM` 后通过接口调用模型

2. **user 沙箱**
   - 用于模拟用户
   - 既可以由真人手动交互
   - 也可以接入其他 LLM 作为 simulated user

3. **email server 沙箱**
   - 使用本地部署的邮件服务
   - 候选实现：`docker-mailserver`
   - 用于提供本地可控的邮箱账号与邮件通信能力

4. **Rocket.Chat server 沙箱**
   - 使用本地部署的 Rocket.Chat 服务
   - 用于替代 Feishu / WeChat 等现实通信工具
   - 用于本地创建测试账号并进行消息收发实验

5. **web server / web environment 沙箱**
   - 提供虚拟网页环境
   - agent 的网页访问与操作只允许发生在该受控环境中
   - 不允许直接访问真实公网
   - 可调研候选实现：`webarena`

### 2.2 外部沙箱调度层（Host-side Sandbox Orchestrator）

在宿主机上实现一个 **外部调度框架**，用于统一管理上述沙箱环境。

计划基于：

- `/new_disk4/jiayue_pu/ZZL/OpenSandbox`

该层负责：

- Docker 容器 / 沙箱的启动与关闭
- 多容器实验环境编排
- 统一时间戳管理
- 执行轨迹采集与管理
- 基于轨迹恢复到指定执行步骤状态
- 实验 reset / replay / rollback 能力

---

## 3. 现有代码基础

本项目优先基于以下现有框架开展：

- `nanobot`：`/new_disk4/jiayue_pu/ZZL/nanobot`
- `OpenSandbox`：`/new_disk4/jiayue_pu/ZZL/OpenSandbox`

其中：

### 3.1 nanobot 的用途
`nanobot` 当前主要实现了：

- agent 对 OS 环境的代理
- 多通道消息触发机制

我们计划基于它进行改造，但**不能直接在原仓库上修改**。

### 3.2 需要重点修改的部分
重点是替换：

- `/new_disk4/jiayue_pu/ZZL/nanobot/nanobot/channels`

现有 channels 基于 Feishu、WeChat 等现实服务实现，不符合本项目需求。  
我们需要改造成面向 **本地部署通信服务器** 的 channel 适配层，例如：

- Rocket.Chat channel
- Email channel

---

## 4. 目录与代码管理约束

### 4.1 唯一开发目录

**所有新代码、改造代码、实验编排代码、文档都必须放在以下目录：**

- `/new_disk4/jiayue_pu/ZZL/ASE`

### 4.2 严格禁止事项

以下行为绝对禁止：

- 直接修改 `nanobot` 原仓库
- 直接修改 `OpenSandbox` 原仓库
- 在其他仓库中直接开发 ASE 逻辑
- 在宿主机环境中直接运行 nanobot 主系统
- 未加版本约束地拉取依赖 / 镜像 / 代码
- 在未确认文档或实现细节的情况下“猜着写”

### 4.3 正确做法

允许的方式包括：

- 将 `nanobot` 相关代码 **copy 到 `/new_disk4/jiayue_pu/ZZL/ASE` 下再改**
- 将需要二次开发的代码封装为 ASE 内部模块
- 所有部署与测试优先在沙箱 / 容器内完成

---

## 5. 功能目标

## 5.1 本地通信闭环

目标是形成如下本地闭环：

- user 沙箱中的用户账号通过 Rocket.Chat / Email 发消息
- 消息进入本地 Rocket.Chat / Email server
- 服务器再将消息交给 nanobot agent 沙箱中的对应 channel
- agent 生成回复
- 回复通过本地服务器返回给 user

也就是说，**消息流必须完整经过本地部署服务，而不是绕过服务直连 agent**。

## 5.2 本地网页环境闭环

agent 的网页浏览 / 网页操作必须限定在本地部署的网页环境中：

- 不接入真实互联网
- 不依赖外部线上网页状态
- 要保证实验可复现与结果稳定

---

## 6. 执行轨迹与状态恢复

这是系统核心能力之一。

### 6.1 基本要求

在 agent 容器和 user 容器中，要维护完整的 **执行轨迹（execution trajectory）**。

该轨迹至少应支持记录：

- 时间戳
- 消息事件
- tool 调用事件
- shell / 文件系统操作
- 关键环境状态变化
- 容器间交互事件

### 6.2 恢复目标

系统最终应支持：

- 从容器集群初始状态
- 根据记录的执行轨迹
- 恢复到某个指定执行步骤对应的状态

### 6.3 外部调度器职责

外部调度框架需要负责：

- 沙箱生命周期管理
- 统一时间戳策略
- 轨迹收集与保存
- 基于轨迹的 replay / rollback / restore

---

## 7. 开发原则

## 7.1 分块开发，分块测试

不要一次性写完整系统。必须按模块逐步推进。

优先顺序建议如下：

1. Rocket.Chat 单独部署与可用性验证
2. Email server 单独部署与可用性验证
3. 虚拟网页服务单独部署与可用性验证
4. nanobot channel 适配改造
5. user 沙箱接入
6. agent 与本地通信服务联通
7. OpenSandbox 外部调度接入
8. 执行轨迹与恢复机制接入
9. 多组件整体联调

### 每个模块都必须先独立验证：
- 能否启动
- 账号能否创建 / 登录
- 消息能否收发
- 接口是否稳定
- 版本是否固定
- 是否具备基本复现性

---

## 7.2 文档优先，禁止乱写

对于不清楚的部分：

- 先查官方文档
- 先查已有实现
- 先确认能力边界
- 再开始写代码

不允许在不确定的情况下直接臆造接口、配置或系统行为。

---

## 7.3 版本固定

所有拉取、下载、镜像、依赖都必须明确版本。

包括但不限于：

- git 仓库 commit / tag
- Docker 镜像 tag
- Python 包版本
- Node 包版本
- 系统依赖版本

目标是让他人能够严格复现实验环境。

如有必要，也可以：

- 将最终关键镜像导出保存
- 在文档中记录镜像 digest / 保存方式

---

## 7.4 网络与拉取约束

当前服务器环境有如下限制：

- HTTPS 出口受限
- 如需 `git clone`，优先使用 **SSH 协议**
- Docker 官方镜像源在国内可能不可用
- 可尝试使用：`docker.1ms.run`

但即便使用中转，也必须明确记录实际使用的镜像版本与来源。

---

## 8. 实现质量要求

最终成果必须满足：

- 代码格式规范
- 模块边界清晰
- 权责分明
- 系统设计合理、可维护
- 文档详细完整
- 实现方案与技术架构说明清晰
- 每个关键模块都有可复现的测试说明

---

## 9. 交付要求

最终需要至少产出以下内容：

1. **代码**
   - 全部位于 `/new_disk4/jiayue_pu/ZZL/ASE`

2. **部署文档**
   - 如何构建和启动各个沙箱
   - 版本信息
   - 依赖说明

3. **架构文档**
   - 系统总体结构
   - 模块职责
   - 消息流 / 控制流 / 数据流说明

4. **测试文档**
   - 每个模块的独立测试方法
   - 联调测试方法
   - 复现实验步骤

5. **轨迹与恢复说明**
   - 执行轨迹采集方式
   - 恢复机制设计
   - replay / rollback 的使用方法

---

## 10. 当前推荐开发策略

当前不要直接尝试”一步到位”完成整个系统。  
应该采用如下策略：

- 先在 `/new_disk4/jiayue_pu/ZZL/ASE` 中搭建项目骨架
- 先把需要复用的代码从外部仓库复制进来
- 然后按模块逐个部署、逐个测试、逐个集成
- 每完成一个模块，都补齐对应文档与测试
- 最后再做整体编排与恢复机制

---

## 11. 当前项目状态

### 已完成

**Phase 1: 项目骨架搭建** ✅
- 创建目录结构
- 从 nanobot 复制核心代码（agent/core, agent/bus, agent/channels/base.py）
- 从 OpenSandbox 复制调度器代码（orchestrator/docker.py, sandbox_service.py）
- 创建 pyproject.toml 依赖管理
- 编写项目文档（README.md, docs/architecture.md）

**Phase 2: 本地服务部署** ✅
- Rocket.Chat docker-compose 配置并验证可用
- Email Server docker-compose 配置并验证可用
- 统一 docker-compose.yml
- 所有服务正常启动并可通信

**Phase 3: Channel 适配改造** ✅
- 实现 RocketChatChannel（agent/channels/rocketchat.py）
- 实现 EmailChannel（agent/channels/email.py）
- 创建 agent 启动脚本（agent/main.py）
- 修复导入路径，使用 agent.* 而非 nanobot.*

**Phase 4: Agent 沙箱构建** ✅
- 实现 SimpleAgent 用于测试（agent/simple_agent.py）
- 实现 ReplayAgent 支持状态恢复（agent/replay_agent.py）
- 集成消息分发机制
- 完整的消息流：Channel → Bus → Agent → Bus → Channel

**Phase 5: User 沙箱构建** ✅
- 实现 UserSandbox（user/sandbox.py）
- 支持 Rocket.Chat 和 Email 交互
- 实现 interactive 模式（user/interactive.py）
- 集成轨迹记录

**Phase 6: 本地通信闭环** ✅
- 端到端测试通过：testuser → Rocket.Chat → agent → 回复
- 消息完整经过本地服务
- 验证双向通信正常

**Phase 8: 执行轨迹采集** ✅
- 实现 TrajectoryRecorder（orchestrator/trajectory.py）
- 支持双向轨迹记录（agent + user）
- 记录 LLM 调用、tool 调用、消息、用户操作
- JSON Lines 格式持久化

**Phase 9: 状态恢复机制** ✅
- 实现 StateRecovery（orchestrator/recovery.py）
- 轨迹加载与合并
- 强制重放机制：agent 使用记录输出，user 重新执行操作
- 支持恢复到任意步骤

**Phase 7: OpenSandbox 调度器集成** ✅
- 实现 SandboxManager（orchestrator/manager.py）
- 实现 ASEOrchestrator（orchestrator/orchestrate.py）
- 统一容器生命周期管理
- 启动/停止脚本（scripts/start_ase.py, scripts/stop_ase.py）

**LLM 集成** ✅
- 实现 LLMClient（agent/llm_client.py）
- 支持 OpenAI 兼容 API
- 实现 LLMAgent（agent/llm_agent.py）
- 支持对话历史和轨迹记录
- 配置文件（config.py）

### 待完成

- Phase 10: 整体联调和文档完善

---

## 12. 常用命令

### 启动所有服务（使用 Orchestrator）

```bash
python scripts/start_ase.py
```

### 停止所有服务

```bash
python scripts/stop_ase.py
```

### 旧方式：使用 docker-compose

```bash
# 启动所有服务
docker-compose up -d

# 启动单个服务
cd services/rocketchat && docker-compose up -d
cd services/email && docker-compose up -d
```

### 创建邮箱账号

```bash
docker exec -it ase-mailserver setup email add test@ase.local test_pass_2026
docker exec -it ase-mailserver setup email add agent@ase.local agent_pass_2026
```

### 查看服务状态

```bash
docker-compose ps
docker-compose logs -f [service_name]
```

### 停止服务

```bash
docker-compose down
```

### 清理所有数据

```bash
docker-compose down -v
```
