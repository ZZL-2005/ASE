# Rocket.Chat 部署指南

## 版本信息

- Rocket.Chat: 6.5.0
- MongoDB: 6.0
- 镜像源: docker.1ms.run

## 启动服务

```bash
cd services/rocketchat
docker-compose up -d
```

## 验证服务

1. 访问 http://localhost:3000
2. 首次访问会进入设置向导
3. 创建管理员账号

## 创建测试账号

通过管理员界面创建测试用户：
- 用户名: test_user
- 邮箱: test@ase.local
- 密码: test_pass_2026

## API 访问

REST API 端点: http://localhost:3000/api/v1
WebSocket: ws://localhost:3000/websocket

## 停止服务

```bash
docker-compose down
```

## 清理数据

```bash
docker-compose down -v
```
