# CampusHub 校园活动预约与分享平台

[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-4.0-brightgreen.svg)](https://spring.io/projects/spring-boot)
[![Vue](https://img.shields.io/badge/Vue-3.5-brightgreen.svg)](https://vuejs.org/)
[![uni-app](https://img.shields.io/badge/uni--app-Mobile-blue.svg)](https://uniapp.dcloud.net.cn/)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)

## 在线体验

- Web 体验入口：https://sun227454.online/CampusHub
- API 基础地址：https://sun227454.online/CampusHub/api/v1
- Android APK：请在 GitHub Releases 下载 `CampusHubApp.apk`

CampusHub 是一个面向校园用户的活动预约、动态分享与 AI 助手系统。项目采用前后端分离架构，包含 Vue Web 端、uni-app 移动端、Spring Boot 后端和 Python AI Agent，并提供 Docker 镜像包部署脚本，适合课程展示、局域网演示和服务器生产部署。

## 当前能力

- 活动预约：发布活动、分页浏览、筛选、查看详情、编辑、取消、完成活动。
- 申请协作：申请加入、撤销申请、发布者审核、接受申请人、查看申请列表。
- 校园动态：发布图文/视频动态、关联活动、搜索动态、详情查看、评论、嵌套回复、点赞。
- 用户体系：邮箱验证码注册、登录、退出、忘记密码、资料编辑、头像上传、公开用户主页。
- AI 助手：多 Agent 校园助手，支持活动检索/创建/申请、动态互动、用户查询、地图天气查询和 SSE 流式回复。
- 管理后台：用户管理、订单管理、内容/评论审核、文件资源管理、AI 会话审计、系统设置、操作日志和仪表盘。
- 工程化：Web/App 本地开发、Docker 多阶段构建、Nginx 反向代理、生产 Compose、镜像包上传部署和 smoke test。

## 演示截图

> 以下演示图片为项目原有截图，保留用于 README 展示。

![image-20260617225533270](https://raw.githubusercontent.com/SunJianBai/pictures/main/img/20260617225533798.png)

![image-20260617225650918](https://raw.githubusercontent.com/SunJianBai/pictures/main/img/20260617225651116.png)

![image-20260617230407359](https://raw.githubusercontent.com/SunJianBai/pictures/main/img/20260617230407686.png)

## 系统架构

```text
CampusHubApp (uni-app)
CampusHubWeb (Vue 3 + Vite + Element Plus)
          |
          | HTTP / SSE / uploads
          v
CampusHubBackend (Spring Boot + JPA + MySQL)
          |
          | HTTP
          v
CampusHubAgent (FastAPI + LangChain/LangGraph)
          |
          | LLM / MCP
          v
SiliconFlow Qwen + AMap MCP
```

生产环境中，`campushub_frontend` 通过 Nginx 暴露 80 端口，并将 `/api/**` 和 `/uploads/**` 反向代理到后端容器。后端连接 Docker Compose 中的 MySQL 服务，并通过 `AGENT_PYTHON_BASE_URL` 调用 Python Agent。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| Web 前端 | Vue 3, Vite, Element Plus, Pinia, Axios |
| 移动端 | uni-app, Vue, HBuilderX, H5/Android 打包 |
| Java 后端 | Spring Boot 4, JDK 21, Spring Data JPA, MySQL 8 |
| AI Agent | FastAPI, LangChain, LangGraph, httpx |
| AI 能力 | SiliconFlow Qwen, 高德地图 MCP |
| 部署 | Docker, Docker Compose, Nginx, PowerShell/SSH 脚本 |

## 目录结构

```text
CampusHubBackend/   Spring Boot 后端服务
CampusHubWeb/       Vue Web 前端
CampusHubApp/       uni-app 移动端
CampusHubAgent/     Python AI Agent 服务
docs/               需求分析、系统分析、CI/CD 与接口文档
scripts/            本地构建、镜像打包、服务器部署和 smoke test 脚本
docker-compose.prod.yml
DOCKER.md
```

## 本地开发

### 1. 后端

```powershell
cd CampusHubBackend
.\mvnw.cmd spring-boot:run
```

默认后端地址为 `http://localhost:8080`，API 前缀为 `/api/v1`。开发环境数据库连接位于 `CampusHubBackend/src/main/resources/application.properties`，生产环境通过 Compose 环境变量覆盖。

### 2. Web

```powershell
cd CampusHubWeb
npm install
npm run dev
```

Web 开发服务默认运行在 `http://localhost:5173`，开发代理会将 `/api` 转发到 `http://localhost:8080`。

### 3. 移动端 H5

```powershell
cd CampusHubApp
$env:UNI_INPUT_DIR='.'
npm.cmd run dev:h5 -- --host 127.0.0.1 --port 5173
```

`CampusHubApp/utils/config.js` 中 H5 和 App 默认使用生产地址 `http://124.220.81.104/api/v1`。如需调试本地后端，可在运行环境中设置 `uni.setStorageSync('env', 'dev')`。

### 4. AI Agent

```powershell
cd CampusHubAgent
uvicorn app.main:app --host 0.0.0.0 --port 5001
```

Agent 需要配置 `SILICONFLOW_API_KEY`、`SILICONFLOW_MODEL`、`JAVA_BACKEND_URL`、`AMAP_MCP_URL` 等环境变量。生产部署时这些变量来自服务器 `.env.prod`。

## API 概览

后端统一前缀：`/api/v1`

| 模块 | 路径 | 说明 |
| --- | --- | --- |
| 认证 | `/auth` | 登录、注册、退出、忘记密码 |
| 验证码 | `/verify` | 邮箱验证码发送和校验 |
| 用户 | `/users` | 用户资料、头像、公开主页、搜索 |
| 活动 | `/orders` | 活动发布、查询、申请、审核、消息 |
| 动态 | `/contents` | 动态、媒体、评论、点赞 |
| 上传 | `/upload` | 图片、视频、头像上传 |
| AI | `/agent` | 会话、消息、流式回复、记忆 |
| 管理 | `/admin` | 后台管理、审计、系统设置 |
| 系统 | `/system` | 公共系统配置与维护状态 |

当前实现中，后端安全配置允许接口进入业务层，业务身份主要通过前端注入的 `X-User-Id` 识别。管理接口额外通过管理员拦截器校验当前用户类型。

## 生产部署

项目提供“本地构建镜像包，再复制到服务器加载部署”的流程，适合服务器公网拉镜像不稳定的情况。

### 构建镜像

```powershell
.\scripts\build-images.ps1 -Tag <release-tag>
.\scripts\save-images.ps1 -Tag <release-tag>
```

生成文件：

```text
artifacts/campushub-images-<release-tag>.tar
```

### 上传并部署

```powershell
.\scripts\deploy-images.ps1 -Tag <release-tag> -HostAlias TX4H4G -PublicBaseUrl http://124.220.81.104
```

脚本会完成：

- 上传镜像包到 `/home/ubuntu/CampusHub/releases/`
- 同步 `docker-compose.prod.yml` 与 `scripts/server/*.sh`
- 在服务器执行 `scripts/server/deploy-release.sh`
- `docker load` 加载镜像
- 通过 `CAMPUSHUB_IMAGE_TAG` 切换 Agent、Backend、Web 镜像
- 保留服务器原有 MySQL 容器和 `db_data` 数据卷
- 运行服务器内部 smoke test 和本地公网 smoke test

生产服务器私有配置保存在服务器 `/home/ubuntu/CampusHub/.env.prod`，不要提交 `.env`、密钥、镜像包、APK、keystore 或运行日志。

## 验证方式

```powershell
.\scripts\smoke-test.ps1 -BaseUrl http://124.220.81.104
```

该脚本验证：

- 首页可以通过公网访问
- `/api/v1/orders?page=1&size=1` 返回 `code=200`

移动端验证重点：

- App/H5 能连接 `http://124.220.81.104/api/v1`
- 登录后请求会携带 `Authorization` 和 `X-User-Id`
- 图片、视频、头像通过 `http://124.220.81.104/uploads/**` 访问
- AI SSE、动态列表、订单列表和详情页能正常加载

## 文档

- [CI/CD 文档](docs/CI-CD.md)
- [AI Agent 架构与优化演进](docs/AI-Agent架构与优化演进.md)
- [接口文档](docs/SystemAnalysis/接口文档.md)
- [Controller-Service 对接文档](docs/SystemAnalysis/controller-service对接文档.md)
- [数据库模型设计](docs/SystemAnalysis/数据库模型设计.md)
- [uni-app 移动端说明](CampusHubApp/README.md)
- [Docker 说明](DOCKER.md)

## 许可证

本项目为课程设计与学习项目，仅供学习交流使用。
