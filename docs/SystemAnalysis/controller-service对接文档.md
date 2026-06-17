# Controller层与Service层对接文档

## 1. 文档说明

### 1.1 文档目的

本文档用于规范Controller层与Service层之间的接口设计，明确Service层需要提供的接口方法、参数列表、返回数据结构、异常处理机制及业务逻辑要求，确保后续Service层开发人员能够无缝对接Controller层，提高团队协作效率。

### 1.2 适用范围

本文档适用于校园约伴系统后端开发，仅针对Controller层与Service层之间的接口设计，不涉及Service层内部实现细节。

### 1.3 术语定义

* **DTO**：数据传输对象（Data Transfer Object），用于Controller层与Service层之间的数据传输
* **API**：应用程序编程接口（Application Programming Interface）
* **JWT**：JSON Web Token，用于用户认证

## 2. 功能模块实现状态总览

| 功能模块       | 控制器实现状态 | Service接口实现状态 | Service实现状态 |
| -------------- | -------------- | ------------------- | --------------- |
| 用户认证模块   | ✅ 已完成      | ✅ 已完成           | ✅ 已完成       |
| 用户管理模块   | ✅ 已完成      | ✅ 已完成           | ✅ 已完成       |
| 预约订单模块   | ✅ 已完成      | ✅ 已完成           | ✅ 已完成       |
| 动态管理模块   | ✅ 已完成      | ✅ 已完成           | ✅ 已完成       |
| 管理员功能模块 | ✅ 已完成      | ✅ 已完成           | ✅ 已完成       |
| 文件上传模块   | ✅ 已完成      | ✅ 已完成           | ✅ 已完成       |

## 3. 服务层接口设计与实现状态

### 3.1 AuthService接口

#### 已完成：

- [X] 接口定义

#### 已完成：

- [X] 接口实现

```java
public interface AuthService {
  
    /**
     * 用户登录
     * @param request 登录请求参数
     * @return LoginResponse 登录响应，包含token和用户信息
     * @throws BusinessException 用户名或密码错误时抛出
     */
    LoginResponse login(LoginRequest request);
  
    /**
     * 用户注册
     * @param request 注册请求参数
     * @return Long 注册成功的用户ID
     * @throws BusinessException 邮箱已存在时抛出
     */
    Long register(RegisterRequest request);
  
    /**
     * 刷新Token
     * @param refreshToken 刷新Token
     * @return String 新的访问Token
     * @throws BusinessException 刷新Token无效时抛出
     */
    String refreshToken(String refreshToken);
  
    /**
     * 用户退出登录
     */
    void logout();

    /**
     * 忘记密码 - 验证邮箱是否已注册
     * @param request 邮箱验证请求参数
     * @return ForgotPasswordVerifyEmailResponse 包含脱敏邮箱
     */
    ForgotPasswordVerifyEmailResponse verifyEmailForReset(ForgotPasswordVerifyEmailRequest request);

    /**
     * 忘记密码 - 校验验证码是否正确且未过期；该步骤不消费验证码
     * @param request 验证码校验请求参数
     */
    void verifyResetCode(ForgotPasswordVerifyCodeRequest request);

    /**
     * 忘记密码 - 再次校验验证码并重置密码；保存成功后标记验证码为已使用
     * @param request 重置密码请求参数
     */
    void resetPassword(ForgotPasswordResetPasswordRequest request);
}
```

### 3.2 UserService接口

#### 已完成：

- [X] 接口定义

#### 已完成：

- [X] 接口实现

```java
public interface UserService {
  
    /**
     * 获取用户详情
     * @param userId 用户ID
     * @return UserInfoResponse 用户信息
     * @throws BusinessException 用户不存在时抛出
     */
    UserInfoResponse getUserInfo(Long userId);
  
    /**
     * 更新用户信息
     * @param userId 用户ID
     * @param request 更新用户信息请求参数
     * @return UserInfoResponse 更新后的用户信息
     * @throws BusinessException 用户不存在时抛出
     */
    UserInfoResponse updateUserInfo(Long userId, UpdateUserRequest request);
  
    /**
     * 修改密码
     * @param userId 用户ID
     * @param request 修改密码请求参数
     * @throws BusinessException 旧密码错误或用户不存在时抛出
     */
    void changePassword(Long userId, ChangePasswordRequest request);
  
    /**
     * 上传头像
     * @param userId 用户ID
     * @param avatar 头像文件
     * @return String 头像URL
     * @throws BusinessException 用户不存在或文件上传失败时抛出
     */
    String uploadAvatar(Long userId, MultipartFile avatar);
  
    /**
     * 搜索用户
     * @param keyword 搜索关键词（昵称或学号）
     * @param page 页码
     * @param size 每页数量
     * @return Object 分页用户列表
     */
    Object searchUsers(String keyword, Integer page, Integer size);
}
```

### 3.3 OrderService接口

#### 已完成：

- [X] 接口定义

#### 已完成：

- [X] 接口实现

```java
public interface OrderService {
  
    /**
     * 发布预约订单
     * @param request 发布订单请求参数
     * @return Long 订单ID
     */
    Long createOrder(CreateOrderRequest request);
  
    /**
     * 获取订单列表
     * @param page 页码
     * @param size 每页数量
     * @param status 订单状态
     * @param activityType 活动类型
     * @param campus 校区
     * @return Object 分页订单列表
     */
    Object getOrders(Integer page, Integer size, OrderStatus status, ActivityType activityType, Campus campus);
  
    /**
     * 获取订单详情
     * @param orderId 订单ID
     * @return Object 订单详情
     */
    Object getOrderDetail(Long orderId);
  
    /**
     * 修改订单信息
     * @param orderId 订单ID
     * @param request 修改订单请求参数
     * @return Long 订单ID
     */
    Long updateOrder(Long orderId, CreateOrderRequest request);
  
    /**
     * 删除订单
     * @param orderId 订单ID
     */
    void deleteOrder(Long orderId);
  
    /**
     * 完成订单
     * @param orderId 订单ID
     */
    void completeOrder(Long orderId);
  
    /**
     * 申请加入订单
     * @param orderId 订单ID
     * @param request 申请加入订单请求参数
     * @return Long 申请记录ID
     */
    Long applyOrder(Long orderId, ApplyOrderRequest request);
  
    /**
     * 取消申请
     * @param orderId 订单ID
     */
    void cancelApply(Long orderId);
  
    /**
     * 获取申请列表
     * @param orderId 订单ID
     * @return Object 申请列表
     */
    Object getApplications(Long orderId);
  
    /**
     * 审核申请
     * @param applyId 申请记录ID
     * @param status 审核状态
     */
    void auditApply(Long applyId, ApplyStatus status);
  
    /**
     * 接受订单
     * @param orderId 订单ID
     * @param accepterId 被接受的用户ID
     */
    void acceptOrder(Long orderId, Long accepterId);
  
    /**
     * 发送订单消息
     * @param orderId 订单ID
     * @param content 消息内容
     * @return Long 消息ID
     */
    Long sendOrderMessage(Long orderId, String content);
  
    /**
     * 获取订单消息
     * @param orderId 订单ID
     * @param page 页码
     * @param size 每页数量
     * @return Object 分页消息列表
     */
    Object getOrderMessages(Long orderId, Integer page, Integer size);
}
```

### 3.4 ContentService接口

#### 已完成：

- [X] 接口定义

#### 已完成：

- [X] 接口实现

```java
public interface ContentService {
  
    /**
     * 发布动态
     * @param request 发布动态请求参数
     * @return Long 动态ID
     */
    Long createContent(CreateContentRequest request);
  
    /**
     * 获取动态列表
     * @param page 页码
     * @param size 每页数量
     * @param type 内容类型
     * @return Object 分页动态列表
     */
    Object getContents(Integer page, Integer size, Integer type);
  
    /**
     * 获取动态详情
     * @param contentId 动态ID
     * @return Object 动态详情
     */
    Object getContentDetail(Long contentId);
  
    /**
     * 删除动态
     * @param contentId 动态ID
     */
    void deleteContent(Long contentId);
  
    /**
     * 上传媒体文件
     * @param contentId 动态ID
     * @param media 媒体文件
     * @return String 媒体文件URL
     */
    String uploadMedia(Long contentId, MultipartFile media);
  
    /**
     * 发布评论
     * @param contentId 动态ID
     * @param request 发布评论请求参数
     * @return Long 评论ID
     */
    Long createComment(Long contentId, CreateCommentRequest request);
  
    /**
     * 获取评论列表
     * @param contentId 动态ID
     * @param page 页码
     * @param size 每页数量
     * @return Object 分页评论列表
     */
    Object getComments(Long contentId, Integer page, Integer size);
  
    /**
     * 点赞/取消点赞
     * @param contentId 内容ID
     * @return Object 包含点赞状态和点赞数
     */
    Object likeContent(Long contentId);
  
    /**
     * 获取点赞列表
     * @param contentId 内容ID
     * @return Object 点赞用户列表
     */
    Object getLikes(Long contentId);
}
```

### 3.5 AdminService接口

#### 已完成：

- [X] 接口定义

#### 已完成：

- [X] 接口实现

```java
public interface AdminService {
  
    /**
     * 获取用户列表（管理员）
     * @param page 页码
     * @param size 每页数量
     * @param userType 用户类型
     * @param userStatus 用户状态
     * @param keyword 搜索关键字
     * @return Object 分页用户列表
     */
    Object getUsers(Integer page, Integer size, UserType userType, UserStatus userStatus, String keyword);
  
    /**
     * 修改用户权限
     * @param userId 用户ID
     * @param userType 用户类型
     */
    void updateUserType(Long userId, UserType userType);

    /**
     * 获取后台订单列表
     * @param page 页码
     * @param size 每页数量
     * @param status 订单状态
     * @param activityType 活动类型
     * @param campus 校区
     * @param keyword 搜索关键词
     * @return Object 分页订单列表
     */
    Object getOrders(Integer page, Integer size, OrderStatus status, ActivityType activityType, Campus campus, String keyword);
  
    /**
     * 管理订单
     * @param orderId 订单ID
     * @param status 订单状态
     */
    void manageOrder(Long orderId, OrderStatus status);
  
    /**
     * 删除任意内容
     * @param contentId 内容ID
     */
    void deleteContent(Long contentId);
  
    /**
     * 获取系统统计
     * 返回用户、订单、报名申请、内容、文件、AI资产等统计值，
     * 其中内容统计包含 pendingPostCount / pendingCommentCount 用于后台待办提醒。
     * @return Object 系统统计数据
     */
    Object getStatistics();
}
```

### 3.6 FileService接口

#### 已完成：

- [X] 接口定义

#### 已完成：

- [X] 接口实现

```java
public interface FileService {
  
    /**
     * 上传图片
     * @param image 图片文件
     * @return String 图片URL
     */
    String uploadImage(MultipartFile image);
  
    /**
     * 上传视频
     * @param video 视频文件
     * @return String 视频URL
     */
    String uploadVideo(MultipartFile video);
}
```

## 4. 控制器实现状态

### 4.1 AuthController

#### 已完成：

- [X] 用户登录接口（POST /auth/login）
- [X] 用户注册接口（POST /auth/register）
- [X] 刷新Token接口（POST /auth/refresh）
- [X] 退出登录接口（POST /auth/logout）

### 4.2 UserController

#### 已完成：

- [X] 获取用户详情接口（GET /users/{userId}）
- [X] 更新用户信息接口（PUT /users/{userId}）
- [X] 修改密码接口（PUT /users/{userId}/password）
- [X] 上传头像接口（POST /users/{userId}/avatar）
- [X] 搜索用户接口（GET /users/search）

### 4.3 OrderController

#### 已完成：

- [X] 发布预约订单接口（POST /orders）
- [X] 获取订单列表接口（GET /orders）
- [X] 获取订单详情接口（GET /orders/{orderId}）
- [X] 修改订单信息接口（PUT /orders/{orderId}）
- [X] 删除订单接口（DELETE /orders/{orderId}）
- [X] 完成订单接口（PUT /orders/{orderId}/complete）
- [X] 申请加入订单接口（POST /orders/{orderId}/apply）
- [X] 取消申请接口（DELETE /orders/{orderId}/apply）
- [X] 获取申请列表接口（GET /orders/{orderId}/applications）
- [X] 审核申请接口（PUT /orders/applications/{applyId}）
- [X] 接受订单接口（POST /orders/{orderId}/accept）
- [X] 发送订单消息接口（POST /orders/{orderId}/messages）
- [X] 获取订单消息接口（GET /orders/{orderId}/messages）

### 4.4 ContentController

#### 已完成：

- [X] 发布动态接口（POST /contents）
- [X] 获取动态列表接口（GET /contents）
- [X] 获取动态详情接口（GET /contents/{contentId}）
- [X] 删除动态接口（DELETE /contents/{contentId}）
- [X] 上传媒体文件接口（POST /contents/{contentId}/media）
- [X] 发布评论接口（POST /contents/{contentId}/comments）
- [X] 获取评论列表接口（GET /contents/{contentId}/comments）
- [X] 点赞/取消点赞接口（POST /contents/{contentId}/like）
- [X] 获取点赞列表接口（GET /contents/{contentId}/likes）

### 4.5 AdminController

> 后台管理接口已注册 `AdminAuthInterceptor`，统一拦截 `/api/v1/admin/**`：请求必须携带管理员用户的 `X-User-Id`；未登录/用户不存在返回 401，普通用户或封禁用户返回 403。该拦截器作为 Controller 入口前置校验，Service 层继续保留业务状态变更和审计日志逻辑。
> 后台管理分页参数在 Service 层统一兜底：`page < 1` 按 `1` 处理，`size < 1` 按 `1` 处理，`size > 100` 按 `100` 处理。
> 后台用户管理在 Service 层保护关键管理员账号：不能取消自己的管理员权限，不能封禁自己，且必须至少保留一个未封禁管理员账号。
> 系统设置保存会在 Service 层清洗范围：`pageSize` 规整到 10-50，`maxUploadSizeMb` 规整到 1-20，避免超过当前 Spring 单文件上传上限。
> 系统设置由 `SystemSettingService` 统一读写和解析；`allowPublicRegistration` 会影响注册验证码和注册提交，`contentAuditEnabled` 会影响新动态/新评论初始状态，`maxUploadSizeMb` 会影响动态媒体、独立上传和头像上传大小限制，`maintenanceNotice` 会通过公开系统信息接口供 Web 前台横幅展示。

#### 已完成：

- [X] 获取用户列表接口（GET /admin/users）
- [X] 获取后台操作日志接口（GET /admin/audit-logs）
- [X] 修改用户权限接口（PUT /admin/users/{userId}/type）
- [X] 修改用户状态接口（PUT /admin/users/{userId}/status）
- [X] 获取后台订单列表接口（GET /admin/orders）
- [X] 管理订单接口（PUT /admin/orders/{orderId}）
- [X] 获取订单申请审核列表接口（GET /admin/order-applications）
- [X] 审核订单申请接口（PUT /admin/order-applications/{applyId}）
- [X] 获取内容审核列表接口（GET /admin/contents）
- [X] 修改内容状态接口（PUT /admin/contents/{contentId}/status）
- [X] 删除任意内容接口（DELETE /admin/contents/{contentId}）
- [X] 获取系统统计接口（GET /admin/statistics）
- [X] 获取文件资源列表接口（GET /admin/files）
- [X] 删除文件资源接口（DELETE /admin/files/{pmid}）
- [X] 获取系统设置接口（GET /admin/settings）
- [X] 更新系统设置接口（PUT /admin/settings）
- [X] 获取AI聚合审计列表接口（GET /admin/ai/audit）
- [X] 获取AI会话审计列表接口（GET /admin/ai/conversations）
- [X] 获取AI记忆审计列表接口（GET /admin/ai/memories）
- [X] 获取AI会话消息详情接口（GET /admin/ai/conversations/{cid}/messages）
- [X] 删除AI会话接口（DELETE /admin/ai/conversations/{cid}）
- [X] 删除AI记忆接口（DELETE /admin/ai/memories/{memId}）

### 4.6 SystemController

#### 已完成：

- [X] 获取公开系统信息接口（GET /system/public-info）

### 4.7 FileController

#### 已完成：

- [X] 上传图片接口（POST /upload/image）
- [X] 上传视频接口（POST /upload/video）

## 5. 异常处理机制

### 5.1 异常类型

Service层需要抛出的异常类型：

* **BusinessException**：业务异常，包含错误码和错误消息
* **RuntimeException**：运行时异常，如空指针异常等

> `BusinessException` 子类会通过构造器绑定具体 `ErrorCode`，例如 `UserNotExistException` 返回 1002、`VerifyCodeErrorException` 返回 1018，前端可直接依赖响应体中的业务码做错误提示与流程分支。

### 5.2 错误码定义

| 错误码 | 说明         |
| ------ | ------------ |
| 1001   | 参数校验失败 |
| 1002   | 用户不存在   |
| 1003   | 密码错误     |
| 1004   | 无权限操作   |
| 1005   | 订单不存在   |
| 1006   | 动态不存在   |
| 1007   | 文件上传失败 |
| 1008   | 重复操作     |
| 1009   | 人数已满     |
| 1010   | 订单已过期   |
| 1011   | 用户已存在   |
| 1012   | 令牌无效     |
| 1013   | 申请记录不存在 |
| 1014   | 订单已完成   |
| 1015   | 订单已取消   |
| 1016   | 评论不存在   |
| 1017   | 非法邮箱地址 |
| 1018   | 验证码错误   |
| 1019   | 文件删除失败 |
| 1020   | 注册失败     |
| 1021   | AI调用异常   |

### 5.3 异常处理流程

1. Service层抛出BusinessException或RuntimeException
2. 全局异常处理器GlobalExceptionHandler捕获异常
3. 根据异常类型和错误码返回统一的错误响应格式
4. 前端根据响应中的错误码和错误消息进行处理

## 6. 数据传输对象

### 6.1 请求DTO

- **LoginRequest**：登录请求参数
- **RegisterRequest**：注册请求参数
- **RefreshTokenRequest**：刷新Token请求参数
- **UpdateUserRequest**：更新用户信息请求参数
- **ChangePasswordRequest**：修改密码请求参数
- **CreateOrderRequest**：创建订单请求参数
- **ApplyOrderRequest**：申请加入订单请求参数
- **AuditApplyRequest**：审核申请请求参数
- **AcceptOrderRequest**：接受订单请求参数
- **SendOrderMessageRequest**：发送订单消息请求参数
- **CreateContentRequest**：发布动态请求参数
- **CreateCommentRequest**：发布评论请求参数

### 6.2 响应DTO

- **ApiResponse**：统一响应格式
- **LoginResponse**：登录响应
- **UserInfoResponse**：用户信息响应
- **PageResponse**：分页响应
- **OrderVO**：订单列表项
- **OrderDetailVO**：订单详情
- **OrderApplyVO**：订单申请记录
- **OrderMessageVO**：订单消息
- **ContentVO**：动态列表项
- **ContentDetailVO**：动态详情
- **CommentVO**：评论
