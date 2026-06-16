# CampusHub CI/CD 实现说明

本文档记录 CampusHub 当前仓库中已经实现的 CI/CD 配置、脚本和服务器部署方式。

## 1. 实现范围

CampusHub 当前使用 GitHub Actions 作为 CI/CD 平台。

- CI workflow：`.github/workflows/ci.yml`
- Deploy workflow：`.github/workflows/deploy.yml`
- 生产编排文件：`docker-compose.prod.yml`
- 生产环境变量示例：`.env.prod.example`
- 本地构建与部署脚本：`scripts/*.ps1`
- 服务器端部署脚本：`scripts/server/*.sh`

当前生产入口：

```text
http://124.220.81.104/
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

## 3. Deploy Workflow

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
public_base_url      可选；默认 http://124.220.81.104
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
.\scripts\run-deploy-workflow.ps1 -ReleaseTag <tag> -UseExistingBundle -PublicBaseUrl http://124.220.81.104
```

## 4. 镜像和 Release Tag

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

## 5. 本地脚本

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
.\scripts\run-deploy-workflow.ps1 -ReleaseTag demo-001 -UseExistingBundle -PublicBaseUrl http://124.220.81.104
```

### deploy-images.ps1

路径：

```text
scripts/deploy-images.ps1
```

作用：从本地直接上传镜像包并在服务器执行部署脚本。

示例：

```powershell
.\scripts\deploy-images.ps1 -Tag demo-001 -PublicBaseUrl http://124.220.81.104
```

### smoke-test.ps1

路径：

```text
scripts/smoke-test.ps1
```

作用：从本地访问公网入口，验证首页和核心 API。

示例：

```powershell
.\scripts\smoke-test.ps1 -BaseUrl http://124.220.81.104
```

验证内容：

```text
http://124.220.81.104/
http://124.220.81.104/api/v1/orders?page=1&size=1
```

该脚本包含重试逻辑，用于处理服务刚重启时短暂未 ready 的情况。

## 6. 服务器端脚本

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

## 7. 服务器目录

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

## 8. 当前实现边界

- CI workflow 会在 PR、push 到 main、手动触发时运行。
- Deploy workflow 由 `workflow_dispatch` 手动触发。
- 仓库中的 workflow 不负责创建或修改 GitHub branch protection rule。
- 是否强制阻止失败 PR 合并，由 GitHub 仓库设置中的分支保护或 ruleset 决定。
- `.env.prod` 只保存在服务器，不提交到 Git。
- 生产入口当前使用 HTTP 80。
