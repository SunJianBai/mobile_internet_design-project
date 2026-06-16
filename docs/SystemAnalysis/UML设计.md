# 校园约伴平台 — UML 设计

> 校内活动预约与分享平台（CampusHub）  
> 基于代码库 `CampusHubBackend` / `CampusHubApp` / `CampusHubWeb` / `CampusHubAgent` 绘制  
> 可使用 [Mermaid Live Editor](https://mermaid.live) 或 VS Code Mermaid 插件预览与导出 PNG/SVG

**Draw.io 可视化源文件**：见 [`drawio/`](./drawio/) 目录，内含 12 张 `.drawio` 图、每张图的说明与 Mermaid 源码，可用 [diagrams.net](https://app.diagrams.net) 直接打开并导出 PNG/PDF。

---

## 1. 用例图（Use Case）

```mermaid
flowchart LR
    subgraph Actors
        U((普通用户))
        A((管理员))
        AI((AI 智能体))
    end

    subgraph 用户与认证
        UC1[注册/登录]
        UC2[找回密码]
        UC3[编辑个人资料]
    end

    subgraph 活动预约
        UC4[发布活动]
        UC5[浏览/搜索活动]
        UC6[申请加入活动]
        UC7[审核申请]
        UC8[活动群聊]
        UC9[完成/取消活动]
    end

    subgraph 动态社区
        UC10[发布动态]
        UC11[评论/点赞]
        UC12[搜索动态]
    end

    subgraph AI 助手
        UC13[AI 对话]
        UC14[预约/地图/天气查询]
    end

    subgraph 管理
        UC15[用户管理]
        UC16[内容/订单审核]
        UC17[数据统计]
    end

    U --> UC1 & UC2 & UC3
    U --> UC4 & UC5 & UC6 & UC8 & UC9
    U --> UC10 & UC11 & UC12
    U --> UC13 & UC14
    U --> UC6 & UC7
    A --> UC15 & UC16 & UC17
    AI -.代理.-> UC4 & UC5 & UC6 & UC10 & UC11 & UC14
```

**说明**：写操作类用例（创建订单、发评论等）在 AI 场景下需用户确认后执行；管理员拥有用户类型变更、强制删帖等扩展权限。

---

## 2. 组件图（Component）

```mermaid
flowchart TB
    subgraph 表现层
        APP[CampusHubApp<br/>uni-app + Vuex]
        WEB[CampusHubWeb<br/>Vue3 + Pinia + Element Plus]
    end

    subgraph 应用层
        API[Spring Boot REST API<br/>:8080 /api/v1]
        SEC[Security + JWT]
        CTRL[Controller 层]
        SVC[Service 层]
        REPO[Repository 层]
    end

    subgraph AI 层
        AGENT[CampusHubAgent<br/>FastAPI + LangGraph :5001]
        MAIN[主 Agent ReAct]
        SUB1[订单子 Agent]
        SUB2[社交子 Agent]
        SUB3[地图天气子 Agent]
        MCP[高德地图 MCP]
        LLM[硅基流动 Qwen API]
    end

    subgraph 数据与外部
        DB[(MySQL)]
        FS[本地/对象存储<br/>图片视频]
        MAIL[邮件验证码]
    end

    APP & WEB -->|HTTP/HTTPS| API
    APP & WEB -->|SSE 流式| API
    API --> SEC --> CTRL --> SVC --> REPO --> DB
    API -->|HTTP 代理| AGENT
    AGENT --> MAIN
    MAIN --> SUB1 & SUB2 & SUB3
    SUB1 & SUB2 -->|backend_client| API
    SUB3 --> MCP
    MAIN & SUB1 & SUB2 & SUB3 --> LLM
    SVC --> FS
    SVC --> MAIL
```

---

## 3. 部署图（Deployment）

```mermaid
flowchart TB
    subgraph 客户端设备
        Phone[手机 / 模拟器<br/>Android/iOS/H5]
        Browser[浏览器<br/>Web 前端]
    end

    subgraph 应用服务器
        JVM[Spring Boot JAR<br/>JDK 21 :8080]
        PY[Python Agent<br/>Uvicorn :5001]
    end

    subgraph 数据与云服务
        MySQL[(MySQL 8.0 :3306)]
        SF[SiliconFlow LLM API]
        AMAP[高德 MCP Server]
        SMTP[邮件服务]
    end

    Phone -->|REST + SSE| JVM
    Browser -->|REST + SSE| JVM
    JVM --> MySQL
    JVM -->|内网 HTTP| PY
    JVM --> SMTP
    PY --> JVM
    PY --> SF
    PY --> AMAP
```

---

## 4. 领域类图（实体 ER / Class）

```mermaid
classDiagram
    direction TB

    class User {
        +Long uid
        +String email
        +String password
        +String nickname
        +String avatarUrl
        +String signature
        +UserType userType
        +UserStatus userStatus
        +LocalDateTime createdAt
        +LocalDateTime lastLoginAt
    }

    class Order {
        +Long oid
        +ActivityType activityType
        +GenderRequire genderRequire
        +Campus campus
        +String location
        +LocalDateTime startTime
        +String note
        +Byte maxPeople
        +Byte currentPeople
        +OrderStatus status
    }

    class OrderApply {
        +Long apid
        +ApplyStatus status
    }

    class OrderAccept {
        +Long acid
        +LocalDateTime acceptedAt
    }

    class OrderMessage {
        +Long mid
        +String content
    }

    class Post {
        +Long pid
        +PostType type
        +String content
        +MediaType hasMedia
        +ContentStatus status
    }

    class PostMedia {
        +Long pmid
        +MediaType mediaType
        +String url
    }

    class PostLike {
        +Long plid
    }

    class AiConversation {
        +Long cid
        +String title
    }

    class AiMessage {
        +Long mid
        +String role
        +String content
        +String toolName
    }

    class AiMemory {
        +Long memId
        +String category
        +String content
    }

    class VerifyCodeRecord {
        +验证码记录
    }

    User "1" --> "*" Order : 发布
    User "1" --> "*" OrderApply : 申请
    User "1" --> "*" OrderMessage : 发送/接收
    Order "1" --> "*" OrderApply : 收到申请
    Order "1" --> "0..1" OrderAccept : 被接受
    Order "1" --> "*" OrderMessage : 群聊
    User "1" --> "*" Post : 发布
    Post "0..1" --> "*" Post : 父评论
    Post "*" --> "0..1" Order : 关联活动
    Post "1" --> "*" PostMedia : 媒体
    Post "1" --> "*" PostLike : 点赞
    User "1" --> "*" PostLike : 点赞
    User "1" --> "*" AiConversation : 拥有
    AiConversation "1" --> "*" AiMessage : 消息
    User "1" --> "*" AiMemory : 偏好记忆
```

---

## 5. 后端分层类图（简化）

```mermaid
classDiagram
    direction LR

    class AuthController
    class UserController
    class OrderController
    class ContentController
    class AgentController
    class FileController
    class AdminController

    class AuthService {
        <<interface>>
        +login()
        +register()
        +refreshToken()
    }
    class OrderService {
        <<interface>>
        +createOrder()
        +applyToOrder()
        +acceptApplicant()
    }
    class ContentService {
        <<interface>>
        +createPost()
        +likeContent()
    }
    class AgentService {
        <<interface>>
        +sendMessage()
        +streamMessage()
    }

    class AuthServiceImpl
    class OrderServiceImpl
    class ContentServiceImpl
    class AgentServiceImpl
    class AgentStreamService

    class UserRepository
    class OrderRepository
    class PostRepository
    class AiConversationRepository

    AuthController --> AuthService
    UserController --> UserService
    OrderController --> OrderService
    ContentController --> ContentService
    AgentController --> AgentService
    AgentController --> AgentStreamService

    AuthService <|.. AuthServiceImpl
    OrderService <|.. OrderServiceImpl
    ContentService <|.. ContentServiceImpl
    AgentService <|.. AgentServiceImpl

    AuthServiceImpl --> UserRepository
    OrderServiceImpl --> OrderRepository
    ContentServiceImpl --> PostRepository
    AgentServiceImpl --> AiConversationRepository
    AgentServiceImpl --> PythonAgentClient
```

---

## 6. AI 多智能体类图（概念）

```mermaid
classDiagram
    class MainAgent {
        +ReAct 循环
        +整合子 Agent 结果
    }

    class OrderSubAgent {
        +search_orders
        +create_order
        +apply_to_order
        +accept_applicant
    }

    class SocialSubAgent {
        +search_contents
        +create_comment
        +like_content
        +search_users
    }

    class MapSubAgent {
        +maps_text_search
        +maps_weather
        +maps_direction_*
    }

    class BackendClient {
        +HTTP 调用 Java API
    }

    class ChatOpenAI {
        +Qwen3-32B
    }

    MainAgent --> OrderSubAgent : call_order_agent
    MainAgent --> SocialSubAgent : call_social_agent
    MainAgent --> MapSubAgent : call_map_agent
    OrderSubAgent --> BackendClient
    SocialSubAgent --> BackendClient
    MainAgent --> ChatOpenAI
    OrderSubAgent --> ChatOpenAI
    SocialSubAgent --> ChatOpenAI
    MapSubAgent --> ChatOpenAI
```

---

## 7. 时序图 — 用户登录

```mermaid
sequenceDiagram
    actor U as 用户
    participant C as App/Web
    participant AC as AuthController
    participant AS as AuthServiceImpl
    participant UR as UserRepository
    participant DB as MySQL

    U->>C: 输入邮箱与密码
    C->>AC: POST /api/v1/auth/login
    AC->>AS: login(LoginRequest)
    AS->>UR: findByEmail(email)
    UR->>DB: SELECT users
    DB-->>UR: User
    UR-->>AS: User
    AS->>AS: 校验密码 + 生成 JWT
    AS-->>AC: Token + 用户信息
    AC-->>C: ApiResponse
    C-->>U: 跳转首页，存储 Token
```

---

## 8. 时序图 — 申请加入活动

```mermaid
sequenceDiagram
    actor P as 发布者
    actor A as 申请者
    participant C as 客户端
    participant OC as OrderController
    participant OS as OrderServiceImpl
    participant DB as MySQL

    A->>C: 浏览活动详情
    C->>OC: POST /orders/{id}/apply
    OC->>OS: applyToOrder(orderId, userId)
    OS->>DB: INSERT order_apply (PENDING_REVIEW)
    DB-->>OS: OK
    OS-->>C: 申请成功

    P->>C: 查看申请列表
    C->>OC: GET /orders/{id}/applications
    OC->>OS: listApplications()
    OS-->>C: 申请列表

    P->>C: 通过某申请
    C->>OC: PUT /applications/{applyId}
    OC->>OS: acceptApplicant()
    OS->>DB: 更新 apply 状态 + current_people
    OS-->>C: 已通过

    A->>C: 进入活动群聊
    C->>OC: POST /orders/{id}/messages
    OC->>OS: sendMessage()
    OS->>DB: INSERT order_messages
```

---

## 9. 时序图 — AI 流式对话（SSE）

```mermaid
sequenceDiagram
    actor U as 用户
    participant C as 客户端
    participant AG as AgentController
    participant AS as AgentStreamService
    participant PY as Python Agent :5001
    participant LLM as Qwen API
    participant DB as MySQL

    U->>C: 发送消息
    C->>AG: POST .../messages/stream (SSE)
    AG->>AS: streamMessage(userId, cid, text)
    AS->>DB: 保存 user 消息
    AS->>PY: POST /chat/stream + history + memory
    loop ReAct 循环
        PY->>LLM: 推理
        opt 需要子 Agent
            PY->>PY: call_order/social/map_agent
            PY->>AS: 经 BackendClient 调 Java API
        end
    end
    PY-->>AS: SSE token 流
    AS-->>C: 转发 SSE 事件
    C-->>U: 逐字显示回复
    AS->>DB: 保存 assistant 消息
    opt 提取用户记忆
        AS->>DB: UPSERT ai_memories
    end
```

---

## 10. 状态图 — 订单生命周期

```mermaid
stateDiagram-v2
    [*] --> PENDING: 用户发布活动

    PENDING --> MATCHED: 人数满/接受申请
    PENDING --> CANCELLED: 发布者取消
    PENDING --> EXPIRED: 超过开始时间未匹配

    MATCHED --> IN_PROGRESS: 活动开始
    MATCHED --> CANCELLED: 发布者取消

    IN_PROGRESS --> COMPLETED: 发布者标记完成
    IN_PROGRESS --> CANCELLED: 异常取消

    COMPLETED --> [*]
    CANCELLED --> [*]
    EXPIRED --> [*]

    note right of PENDING
        OrderStatus 枚举
        对应 Order.status 字段
    end note
```

---

## 11. 状态图 — 活动申请

```mermaid
stateDiagram-v2
    [*] --> PENDING_REVIEW: 用户提交申请

    PENDING_REVIEW --> APPROVED: 发布者通过
    PENDING_REVIEW --> REJECTED: 发布者拒绝
    PENDING_REVIEW --> WITHDRAWN: 申请人撤回

    APPROVED --> [*]
    REJECTED --> [*]
    WITHDRAWN --> [*]
```

---

## 12. 活动图 — 发布动态（含媒体）

```mermaid
flowchart TD
    Start([开始]) --> Auth{已登录?}
    Auth -->|否| Login[跳转登录]
    Auth -->|是| Edit[编辑正文]
    Edit --> HasMedia{含图片/视频?}
    HasMedia -->|是| Upload[POST /upload/image|video]
    Upload --> Create[POST /api/v1/contents]
    HasMedia -->|否| Create
    Create --> Attach{有媒体?}
    Attach -->|是| Media[POST /contents/{id}/media]
    Attach -->|否| Done
    Media --> Done([发布成功，刷新列表])
    Login --> End([结束])
    Done --> End
```

---

## 13. 包图（Package）— 后端模块划分

```mermaid
flowchart TB
    subgraph dev.campushubbackend
        controller[controller<br/>REST 入口]
        service[service + impl<br/>业务逻辑]
        repository[repository<br/>JPA 数据访问]
        entity[entity<br/>领域实体]
        dto[dto<br/>请求/响应对象]
        enums[enums<br/>枚举常量]
        config[config<br/>安全/CORS/WebMvc]
        exception[exception<br/>统一异常]
        utils[utils<br/>工具类]
    end

    controller --> service
    service --> repository
    repository --> entity
    controller --> dto
    entity --> enums
    service --> dto
    controller --> exception
```




---

## 图例与版本

| 图类型 | 用途 |
|--------|------|
| 用例图 | 需求范围、角色与功能边界 |
| 组件/部署图 | 系统架构与运维部署 |
| 类图 | 数据模型与分层设计 |
| 时序图 | 关键业务流程交互 |
| 状态/活动图 | 订单/申请状态与操作流程 |

**文档版本**：v1.0 | **对应代码分支**：CampusHub 主仓库
