# CampusHub CI/CD 录屏文案匹配

本文档对应 CI/CD 展示视频的三段录屏素材，记录每段视频展示的目标、执行命令、成功结果和后期配音稿。

## 第一段：PR 正常通过 CI

### 展示目标

这一段展示 feature 分支提交正常改动后，Pull Request 自动触发 CI，并且所有检查通过。

流程：

```text
feature 分支正常改动
-> 本地构建
-> 提交并推送
-> 创建 Pull Request
-> GitHub Actions 自动运行 CI
-> Backend / Web / Agent / App Config / Docker Build 全部通过
```

### 录屏中的改动

文件：

```text
CampusHubApp/utils/config.js
```

改动内容：

```js
// CI demo: production mode uses the public server entry point.
const prodOrigin = 'http://124.220.81.104'
```

这个改动用于展示正常 feature 分支变更。

### 录屏命令

```powershell
git branch --show-current
git status
```

预期结果：

```text
feature/demo-cicd-pass-rerecord
modified: CampusHubApp/utils/config.js
```

执行自动化脚本：

```powershell
.\scripts\demo-cicd.ps1 `
  -CommitMessage "Demo CI pass workflow" `
  -CreatePr `
  -PrTitle "Demo CI pass workflow" `
  -PrBody "Demo PR showing a successful CI workflow."
```

脚本执行内容：

```text
1. 构建 CampusHubApp H5
2. git add CampusHubApp
3. git commit
4. git push
5. 创建 Pull Request
6. 等待 GitHub Actions CI 完成
```

### 成功结果

终端中出现：

```text
DONE  Build complete.
Create or reuse pull request
Watching workflow run
Run CI (...) completed with 'success'
```

GitHub PR 页面中出现：

```text
Backend       passed
Web           passed
Agent         passed
App Config    passed
Docker Build  passed
```

### 镜头内容

- `CampusHubApp/utils/config.js`：展示 feature 分支的正常改动。
- `.github/workflows/ci.yml`：展示 `pull_request` 触发器。
- `scripts/demo-cicd.ps1`：展示脚本自动执行构建、提交、推送、创建 PR、等待 CI。
- GitHub PR 页面：展示 Checks 全部变绿。

### 配音稿

```text
第一段展示正常 Pull Request 的 CI 流程。

当前我在 feature 分支上做了一个很小的 App 配置改动。接下来运行 demo-cicd.ps1 自动化脚本。脚本会先执行本地 H5 构建，确认 App 端可以正常编译。

构建通过后，脚本会自动提交代码、推送 feature 分支，并在 GitHub 上创建 Pull Request。

因为项目的 ci.yml 配置了 pull_request 触发器，所以 PR 创建后，GitHub Actions 会自动运行 CI。

这里可以看到 CI 分成多个 job：Backend 检查 Java 后端编译，Web 检查前端构建，Agent 检查 Python Agent 导入，App Config 检查 uni-app 配置 JSON，Docker Build 检查生产镜像构建。

最后所有检查都通过，说明这个 PR 已经具备合并到 main 的条件。
```

## 第二段：CI 发现错误

### 展示目标

这一段展示 feature 分支引入错误配置后，Pull Request 自动触发 CI，并且 CI 能发现错误。

流程：

```text
feature 分支引入错误
-> 提交并推送
-> 创建 Pull Request
-> GitHub Actions 自动运行 CI
-> App Config 失败
```

### 录屏中的错误

文件：

```text
CampusHubApp/pages.json
```

错误内容：

```js
// CI_DEMO_INVALID_JSON
```

该内容位于 `pages.json` 末尾，使 JSON 文件变成非法格式。

### 录屏命令

```powershell
git branch --show-current
git status
Get-Content -Tail 8 .\CampusHubApp\pages.json
```

预期结果：

```text
feature/demo-cicd-fail-rerecord
modified: CampusHubApp/pages.json
// CI_DEMO_INVALID_JSON
```

执行自动化脚本：

```powershell
.\scripts\demo-cicd.ps1 `
  -SkipLocalBuild `
  -CommitMessage "Demo CI failure workflow" `
  -Pathspec CampusHubApp/pages.json `
  -CreatePr `
  -PrTitle "Demo CI failure workflow" `
  -PrBody "Demo PR showing CI blocking invalid App config."
```

脚本执行内容：

```text
1. 跳过本地构建
2. git add CampusHubApp/pages.json
3. git commit
4. git push
5. 创建 Pull Request
6. 等待 GitHub Actions CI 完成
```

这里使用 `-SkipLocalBuild`，让错误在 PR CI 阶段被 GitHub Actions 捕获。

### 成功结果

这一段的成功结果是 CI 失败。

终端中出现：

```text
App Config failed
Run CI (...) completed with 'failure'
Workflow failed. workflow=ci.yml
```

GitHub PR 页面中出现：

```text
App Config failed
```

其他 job 可能通过：

```text
Backend       passed
Web           passed
Agent         passed
Docker Build  passed
```

### 镜头内容

- `CampusHubApp/pages.json`：展示非法 JSON 注释。
- `.github/workflows/ci.yml`：展示 `App Config` job。
- GitHub PR 页面：展示 `App Config` 检查失败。

### 配音稿

```text
第二段展示 CI 如何发现错误。

这里我在 feature 分支中故意破坏 CampusHubApp/pages.json，在文件末尾加入一行非法 JSON 注释。这个错误模拟多人协作中某个分支不小心破坏了 App 配置文件。

这次运行脚本时使用 SkipLocalBuild，让错误进入 Pull Request 阶段，由 GitHub Actions 自动检测。

PR 创建后，CI 自动运行。可以看到 Backend、Web、Agent 和 Docker Build 仍然可以通过，但 App Config 失败了。

App Config 这个 job 会解析 CampusHubApp 的 package.json、manifest.json 和 pages.json，因此它准确发现了 pages.json 格式错误。

这一段说明 CI 可以在 PR 阶段发现配置问题，避免错误进入后续流程。
```

## 第三段：CD 发布到服务器

### 展示目标

这一段展示 main 分支上的稳定版本通过 GitHub Actions Deploy workflow 发布到服务器，并通过 smoke test 验证公网网页和 API。

流程：

```text
main 稳定版本
-> 触发 GitHub Actions Deploy workflow
-> SSH 连接服务器
-> 执行服务器部署脚本
-> 切换 release tag
-> External smoke test 通过
```

### 录屏前状态

本次录屏使用 release tag：

```text
f5ba305-cd-demo
```

服务器上已准备镜像包：

```text
/home/ubuntu/CampusHub/releases/campushub-images-f5ba305-cd-demo.tar
```

Deploy workflow 使用预上传镜像包模式：

```text
use_existing_bundle=true
```

### 录屏命令

先展示本地状态：

```powershell
git checkout main
git status
git rev-parse --short HEAD
```

触发 Deploy workflow：

```powershell
.\scripts\run-deploy-workflow.ps1 `
  -ReleaseTag f5ba305-cd-demo `
  -UseExistingBundle `
  -PublicBaseUrl http://124.220.81.104
```

查看服务器发布结果：

```powershell
ssh TX4H4G "cd /home/ubuntu/CampusHub && cat .env.release && sudo docker compose -f docker-compose.prod.yml --env-file .env.prod ps"
```

### workflow 执行内容

GitHub Actions 中的 Deploy workflow 位于：

```text
.github/workflows/deploy.yml
```

本段录屏中的关键步骤：

```text
1. Checkout
2. Resolve release tag
3. Start SSH agent
4. Trust deploy host
5. Prepare remote directories
6. Upload deployment files only
7. Deploy release
8. External smoke test
```

在 `use_existing_bundle=true` 时，以下步骤会跳过：

```text
Build Docker images
Bundle Docker images
Upload release bundle and deployment files
```

### 成功结果

终端和 GitHub Actions 页面中出现：

```text
Deploy release                   passed
External smoke test              passed
Run Deploy (...) completed with 'success'
```

服务器状态中出现：

```text
CAMPUSHUB_IMAGE_TAG=f5ba305-cd-demo
campushub_agent      campushub-agent:f5ba305-cd-demo
campushub_backend    campushub-backend:f5ba305-cd-demo
campushub_frontend   campushub-web:f5ba305-cd-demo
```

公网访问：

```text
http://124.220.81.104/
```

核心 API：

```text
http://124.220.81.104/api/v1/orders?page=1&size=1
```

### 镜头内容

- `.github/workflows/deploy.yml`：展示 `workflow_dispatch`、`Deploy release` 和 `External smoke test`。
- `scripts/run-deploy-workflow.ps1`：展示脚本触发 GitHub Actions Deploy workflow。
- GitHub Actions 页面：展示 Deploy workflow 执行并成功。
- 终端 SSH 输出：展示服务器 release tag 和容器镜像 tag。
- 浏览器：展示 `http://124.220.81.104/` 可以访问。

### 配音稿

```text
第三段展示 CD 发布流程。

当前代码已经在 main 分支上。这里通过 run-deploy-workflow.ps1 触发 GitHub Actions 的 Deploy workflow，并指定发布版本 f5ba305-cd-demo。

Deploy workflow 会通过 SSH 连接服务器，上传部署配置和服务器脚本，然后执行 deploy-release.sh。

部署脚本会在服务器上加载指定 release tag 的镜像，并通过 docker compose 启动新版本服务。

这里可以看到 GitHub Actions 中 Deploy release 和 External smoke test 都执行成功。External smoke test 会从公网访问 CampusHub 首页和核心 API。

最后通过 SSH 查看服务器状态，.env.release 已经切换到 f5ba305-cd-demo，Agent、Backend 和 Web 三个容器也都运行在这个 tag 上。

这说明当前版本已经通过 CD 流程成功发布到服务器。
```
