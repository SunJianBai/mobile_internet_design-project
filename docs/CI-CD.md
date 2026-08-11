# CampusHub CI/CD 实现说明

本文档记录 CampusHub 当前仓库中已经实现的 CI/CD 配置、脚本和服务器部署方式。

## 1. 实现范围

CampusHub 当前使用 GitHub Actions 作为 CI/CD 平台。

- CI workflow：`.github/workflows/ci.yml`
- CD workflow：`.github/workflows/cd.yml`
- 手动 Deploy workflow：`.github/workflows/deploy.yml`
- 生产编排文件：`docker-compose.prod.yml`
- 快速部署编排文件：`docker-compose.fast.yml`
- 生产环境变量示例：`.env.prod.example`
- 本地构建与部署脚本：`scripts/*.ps1`
- 服务器端部署脚本：`scripts/server/*.sh`

当前生产入口：

```text
https://sun227454.online/CampusHub/
```

生产服务器目录：

```text
/home/ubuntu/CampusHub
```

## 2. CI Workflow

CI 文件位于：

```text
.github/workflows/ci.yml
```

触发方式：

```text
pull_request
push 到 main
workflow_dispatch
```

CI 包含 5 个 job。

### Backend

工作目录：

```text
CampusHubBackend
```

执行内容：

```text
使用 Temurin JDK 21
执行 ./mvnw -DskipTests compile
```

作用：验证 Java 后端可以编译。

### Web

工作目录：

```text
CampusHubWeb
```

执行内容：

```text
使用 Node.js 22
执行 npm ci
执行 npm run build
```

作用：验证 Web 前端可以安装依赖并构建。

### Agent

工作目录：

```text
CampusHubAgent
```

执行内容：

```text
使用 Python 3.11
执行 pip install -r requirements.txt
执行 python -s -c "import app.main; print(app.main.app.title)"
```

CI 中使用：

```text
SILICONFLOW_API_KEY=ci-dummy-key
PYTHONNOUSERSITE=1
```

作用：验证 Python Agent 依赖安装和 FastAPI 应用导入。

### App Config

执行内容：

```text
使用 Node.js 22
解析 CampusHubApp/package.json
解析 CampusHubApp/manifest.json
解析 CampusHubApp/pages.json
```

作用：验证 uni-app 端核心 JSON 配置合法。

### Docker Build

依赖 job：

```text
Backend
Web
Agent
```

执行内容：

```text
docker build -t campushub-agent:<ci-tag> CampusHubAgent
docker build -t campushub-backend:<ci-tag> CampusHubBackend
docker build -t campushub-web:<ci-tag> CampusHubWeb
```

作用：验证三个生产镜像可以构建。

## 3. CD Workflow

CD 文件位于：

```text
.github/workflows/cd.yml
```

触发方式：

```text
workflow_run：CI 在 main 分支成功完成后自动触发
workflow_dispatch：手动触发，可指定 deploy_mode 和 modules
```

该 workflow 使用 `production-campushub` concurrency，避免多个生产部署同时执行。

### 自动部署策略

`deploy_mode=auto` 是默认模式。workflow 会根据变更文件选择部署方式：

```text
普通源码变更：走 fast-deploy
依赖、Dockerfile、Nginx 或生产 compose 变化：走 full-deploy
仅文档、测试或无运行时代码变化：跳过部署
```

快速部署识别的模块：

```text
CampusHubAgent/app/**                         -> agent
CampusHubBackend/src/**                       -> backend
CampusHubWeb/src/**、public/**、index.html    -> web
CampusHubWeb/vite.config.*                    -> web
```

需要完整镜像部署的典型文件：

```text
CampusHubAgent/Dockerfile
CampusHubAgent/requirements.txt
CampusHubBackend/Dockerfile
CampusHubBackend/pom.xml
CampusHubBackend/mvnw*
CampusHubBackend/.mvn/**
CampusHubWeb/Dockerfile
CampusHubWeb/package.json
CampusHubWeb/package-lock.json
CampusHubWeb/nginx.conf
docker-compose.prod.yml
```

### Fast Deploy

fast-deploy 不重新构建 Docker 镜像，只构建或打包发生变化的运行产物：

```text
agent   -> 打包 CampusHubAgent/app
backend -> Maven package 后上传 app.jar
web     -> npm run build 后上传 dist
```

GitHub Actions 会生成 `artifacts/campushub-fast-<tag>.tar.gz`，上传到服务器 `/home/ubuntu/CampusHub/fast-artifacts/`，再执行：

```bash
scripts/server/deploy-fast-release.sh <tag> fast-artifacts/campushub-fast-<tag>.tar.gz https://sun227454.online/CampusHub
```

服务器端使用 `docker-compose.fast.yml` 启动业务容器，仍保留 Docker 隔离，但通过只读 bind mount 挂载当前 release：

```text
current/web/dist       -> /usr/share/nginx/html/CampusHub
current/backend/app.jar -> /app/app.jar
current/agent/app      -> /app/app
```

未变化的模块会从上一个 `current` release 复制，因此一次 agent-only 修改通常只需要上传一个很小的源码包并重建 agent/backend/frontend 中必要的服务。

服务器默认通过 `FAST_RELEASE_KEEP=8` 保留最近的快速发布目录，并保护当前版与上一版回滚目标，避免频繁 fast-deploy 持续占满磁盘。

### Full Deploy

full-deploy 会完整构建三个镜像并上传镜像包，适合依赖、Dockerfile 或 Nginx 配置变化。该路径使用 GitHub Actions Buildx cache 减少重复构建时间。

完整部署成功后，`scripts/server/deploy-release.sh` 会从正在运行的容器抽取一份 fast baseline：

```text
/home/ubuntu/CampusHub/fast-releases/full-<tag>
```

这样后续 fast-deploy 可以继续基于最新完整镜像版本复制未变化模块，避免基线过期。

### Fast Rollback

快速部署回滚脚本：

```bash
scripts/server/rollback-fast-release.sh
```

不传参数时会回滚到 `.env.fast.release.previous` 记录的上一版；也可以传入 release tag 或绝对 release 目录。

## 4. Deploy Workflow

Deploy 文件位于：

```text
.github/workflows/deploy.yml
```

触发方式：

```text
workflow_dispatch
```

该 workflow 只在 `main` 分支运行：

```text
github.ref == 'refs/heads/main'
```

输入参数：

```text
release_tag          可选；为空时使用当前 Git commit 短 SHA
public_base_url      可选；默认 https://sun227454.online/CampusHub
use_existing_bundle  可选；默认 false
```

需要配置的 GitHub Actions Secrets：

```text
DEPLOY_HOST      124.220.81.104
DEPLOY_USER      ubuntu
DEPLOY_PORT      22
DEPLOY_SSH_KEY   GitHub Actions 连接服务器用的 SSH 私钥
```

### 标准模式

当 `use_existing_bundle=false` 时，Deploy workflow 执行：

```text
1. Checkout 代码
2. 解析 release tag
3. 构建 campushub-agent:<tag>
4. 构建 campushub-backend:<tag>
5. 构建 campushub-web:<tag>
6. docker save 并 gzip 成 artifacts/campushub-images-<tag>.tar.gz
7. 通过 SCP 上传镜像包、docker-compose.prod.yml 和服务器脚本
8. SSH 到服务器执行 scripts/server/deploy-release.sh
9. 执行 External smoke test
```

### 预上传镜像包模式

当 `use_existing_bundle=true` 时，Deploy workflow 执行：

```text
1. Checkout 代码
2. 解析 release tag
3. 跳过 GitHub Runner 上的镜像构建
4. 跳过 GitHub Runner 上的镜像打包
5. 跳过大镜像包上传
6. 上传 docker-compose.prod.yml 和服务器脚本
7. 使用服务器上已有的 releases/campushub-images-<tag>.tar 或 .tar.gz
8. SSH 到服务器执行 scripts/server/deploy-release.sh
9. 执行 External smoke test
```

预上传镜像包由本地脚本完成：

```powershell
.\scripts\build-images.ps1 -Tag <tag>
.\scripts\save-images.ps1 -Tag <tag>
.\scripts\preload-release-bundle.ps1 -Tag <tag>
```

触发预上传模式 Deploy：

```powershell
.\scripts\run-deploy-workflow.ps1 -ReleaseTag <tag> -UseExistingBundle -PublicBaseUrl https://sun227454.online/CampusHub
```

## 5. 镜像和 Release Tag

生产 compose 中的业务服务镜像通过 `CAMPUSHUB_IMAGE_TAG` 指定版本：

```yaml
campushub-agent:${CAMPUSHUB_IMAGE_TAG:-latest}
campushub-backend:${CAMPUSHUB_IMAGE_TAG:-latest}
campushub-web:${CAMPUSHUB_IMAGE_TAG:-latest}
```

服务器当前 release 记录在：

```text
/home/ubuntu/CampusHub/.env.release
```

内容格式：

```text
CAMPUSHUB_IMAGE_TAG=<tag>
```

上一个 release 记录在：

```text
/home/ubuntu/CampusHub/.env.release.previous
```

## 6. 本地脚本

### build-images.ps1

路径：

```text
scripts/build-images.ps1
```

作用：构建三个业务镜像。

示例：

```powershell
.\scripts\build-images.ps1 -Tag demo-001
```

构建镜像：

```text
campushub-agent:demo-001
campushub-backend:demo-001
campushub-web:demo-001
```

### save-images.ps1

路径：

```text
scripts/save-images.ps1
```

作用：把三个业务镜像保存为 tar 包。

示例：

```powershell
.\scripts\save-images.ps1 -Tag demo-001
```

输出：

```text
artifacts/campushub-images-demo-001.tar
```

### preload-release-bundle.ps1

路径：

```text
scripts/preload-release-bundle.ps1
```

作用：把本地镜像包预上传到服务器 release 目录，并同步部署文件。

示例：

```powershell
.\scripts\preload-release-bundle.ps1 -Tag demo-001
```

服务器目标路径：

```text
/home/ubuntu/CampusHub/releases/campushub-images-demo-001.tar
```

### run-deploy-workflow.ps1

路径：

```text
scripts/run-deploy-workflow.ps1
```

作用：触发 GitHub Actions Deploy workflow，并等待 workflow 结束。

示例：

```powershell
.\scripts\run-deploy-workflow.ps1 -ReleaseTag demo-001 -UseExistingBundle -PublicBaseUrl https://sun227454.online/CampusHub
```

### deploy-images.ps1

路径：

```text
scripts/deploy-images.ps1
```

作用：从本地直接上传镜像包并在服务器执行部署脚本。

示例：

```powershell
.\scripts\deploy-images.ps1 -Tag demo-001 -PublicBaseUrl https://sun227454.online/CampusHub
```

### smoke-test.ps1

路径：

```text
scripts/smoke-test.ps1
```

作用：从本地访问公网入口，验证首页和核心 API。

示例：

```powershell
.\scripts\smoke-test.ps1 -BaseUrl https://sun227454.online/CampusHub
```

验证内容：

```text
https://sun227454.online/CampusHub/
https://sun227454.online/CampusHub/api/v1/orders?page=1&size=1
```

该脚本包含重试逻辑，用于处理服务刚重启时短暂未 ready 的情况。

## 7. 服务器端脚本

服务器端脚本目录：

```text
/home/ubuntu/CampusHub/scripts/server
```

仓库路径：

```text
scripts/server
```

### deploy-release.sh

作用：

```text
1. 读取 release tag 和镜像包路径
2. docker load 加载镜像
3. 写入 .env.release
4. 使用 docker compose up -d --no-build 启动服务
5. 执行服务器内部 smoke test
```

### rollback-release.sh

作用：回滚到 `.env.release.previous` 中记录的上一个 release，或回滚到指定 tag。

### smoke-test.sh

作用：在服务器内部检查首页和 API。

默认内部地址：

```text
http://127.0.0.1
```

## 8. 服务器目录

生产服务器目录结构：

```text
/home/ubuntu/CampusHub/
  .env.prod
  .env.release
  .env.release.previous
  docker-compose.prod.yml
  releases/
  backups/
  scripts/server/
```

Docker volume：

```text
campushub_db_data
campushub_backend_uploads
```

## 9. 当前实现边界

- CI workflow 会在 PR、push 到 main、手动触发时运行。
- CD workflow 会在 main 分支 CI 成功后自动部署，也可手动触发。
- 手动 Deploy workflow 仍保留，用于显式执行完整镜像包发布或复用预上传镜像包。
- 仓库中的 workflow 不负责创建或修改 GitHub branch protection rule。
- 是否强制阻止失败 PR 合并，由 GitHub 仓库设置中的分支保护或 ruleset 决定。
- `.env.prod` 只保存在服务器，不提交到 Git。
- 生产入口当前使用 `https://sun227454.online/CampusHub/`，Caddy 转发到本机 `127.0.0.1:18080` 上的 CampusHub 前端容器。
