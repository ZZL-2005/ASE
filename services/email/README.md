# Email Server 部署指南

## 版本信息

- docker-mailserver: 13.3.1
- 镜像源: docker.1ms.run

## 启动服务

```bash
cd services/email
docker-compose up -d
```

## 创建邮箱账号

```bash
# 创建测试账号
docker exec -it ase-mailserver setup email add test@ase.local test_pass_2026
docker exec -it ase-mailserver setup email add agent@ase.local agent_pass_2026
```

## 验证服务

```bash
# 检查服务状态
docker exec -it ase-mailserver setup debug
```

## 端口说明

- 25: SMTP
- 587: SMTP (submission)
- 143: IMAP
- 993: IMAPS

## 测试邮件收发

使用邮件客户端连接：
- SMTP: localhost:587
- IMAP: localhost:143
- 用户名: test@ase.local
- 密码: test_pass_2026

## 停止服务

```bash
docker-compose down
```
