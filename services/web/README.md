# Web Environment

## 简介

这是一个简单的 nginx 静态网站，用于测试 agent 的网页交互能力。

## 设计原则

接口和结构与 WebArena 兼容，方便将来迁移到完整的 WebArena 环境。

## 访问地址

http://localhost:8080

## 可用页面

- `/` - 首页
- `/search.html` - 搜索页面
- `/form.html` - 表单页面
- `/api.html` - API 信息

## 启动服务

```bash
docker compose up -d webenv
```

## 未来迁移

当需要完整的 WebArena 环境时，只需：
1. 替换 docker-compose.yml 中的 webenv 服务
2. 更新端口和配置
3. Agent 代码无需修改
