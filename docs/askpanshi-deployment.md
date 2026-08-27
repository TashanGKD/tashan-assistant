# askpanshi 部署清单

目标站点使用 `askpanshi.tashan.ac.cn`。该域名已经解析到 `world.tashan.chat` 所在服务器 `8.147.58.40`。用户消息中的 `askpanshi.tanshan.ac.cn` 当前没有 DNS 记录，因此部署采用已解析的域名。

## 验收清单

- [x] 核对目标仓库、Docker 入口和 `/api/health`。
- [x] 核对服务器端口、Nginx、Certbot 和现有容器，选用回环端口 `18082`。
- [x] 增加 Docker 健康检查和仅回环监听的端口配置。
- [x] 增加带生产配置校验、健康轮询和失败回滚的部署脚本。
- [x] 增加 GitHub Actions 部署 workflow，部署前先执行 Python 编译和测试。
- [x] 增加服务器端 `systemd` 定时监控方案，每两分钟检查一次上游 `main`。
- [x] 增加 Nginx、HTTPS 和 Certbot 配置脚本。
- [ ] 在服务器写入真实的 DeepSeek、飞书和管理员配置。
- [ ] 首次启动容器，签发证书并启用 HTTPS vhost。
- [ ] 验证首页、健康接口、真实答疑、飞书 Case 写入和失败回滚。
- [ ] 将变更合并到上游 `main`，并配置 Actions 所需的 SSH secrets。

## 生产环境文件

服务器文件路径为 `/var/www/github-actions/repos/tashan-assistant/.env`。部署脚本要求以下字段都有真实值：

```env
APP_BIND_IP=127.0.0.1
APP_PORT=18082
PYTHON_BASE_IMAGE=docker.m.daocloud.io/library/python:3.12-slim
DEEPSEEK_API_KEY=
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_APP_TOKEN=
FEISHU_CASE_TABLE_ID=
FEISHU_REPORT_TABLE_ID=
ADMIN_TOKEN=
ALLOWED_ORIGINS=https://askpanshi.tashan.ac.cn
```

`.env` 只保存在服务器，不进入 Git。缺少 DeepSeek 或飞书配置时，部署脚本会退出，不会把应用的本地模拟模式当作生产服务。

## GitHub Actions secrets

上游仓库的 `production` 环境需要配置：

```text
DEPLOY_HOST=8.147.58.40
DEPLOY_USER=root
DEPLOY_PORT=22
DEPLOY_PATH=/var/www/github-actions/repos
SSH_PRIVATE_KEY=<deployment private key>
```

workflow 使用仓库只读地址拉取代码。密钥只用于连接部署服务器。

## 服务器监控

`tashan-assistant-deploy.timer` 每两分钟拉取一次 `origin/main`。检测到新提交后，监控脚本先保留当前 SHA，再构建并启动新版本。健康检查未通过时，脚本会检出旧 SHA 并重新构建，随后恢复旧版本。

查看最近一次执行：

```bash
systemctl status tashan-assistant-deploy.timer
journalctl -u tashan-assistant-deploy.service -n 100 --no-pager
```
