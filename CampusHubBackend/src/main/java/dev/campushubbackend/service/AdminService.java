package dev.campushubbackend.service;

import dev.campushubbackend.enums.ApplyStatus;
import dev.campushubbackend.enums.ActivityType;
import dev.campushubbackend.enums.Campus;
import dev.campushubbackend.enums.ContentStatus;
import dev.campushubbackend.enums.OrderStatus;
import dev.campushubbackend.enums.PostType;
import dev.campushubbackend.enums.UserStatus;
import dev.campushubbackend.enums.UserType;
import dev.campushubbackend.enums.MediaType;

import java.util.Map;

/**
 * 管理员服务接口
 */
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
     * 获取后台操作日志
     * @param page 页码
     * @param size 每页数量
     * @param moduleName 模块
     * @param action 动作
     * @param keyword 搜索关键字
     * @return Object 分页日志列表
     */
    Object getAuditLogs(Integer page, Integer size, String moduleName, String action, String keyword);
    
    /**
     * 修改用户权限
     * @param userId 用户ID
     * @param userType 用户类型
     */
    void updateUserType(Long userId, UserType userType);

    /**
     * 修改用户状态
     * @param userId 用户ID
     * @param userStatus 用户状态
     */
    void updateUserStatus(Long userId, UserStatus userStatus);

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
     * 获取订单申请审核列表
     * @param page 页码
     * @param size 每页数量
     * @param status 申请状态
     * @param keyword 搜索关键字
     * @return Object 分页申请列表
     */
    Object getOrderApplications(Integer page, Integer size, ApplyStatus status, String keyword);

    /**
     * 审核订单申请
     * @param applyId 申请ID
     * @param status 审核状态
     */
    void auditOrderApplication(Long applyId, ApplyStatus status);

    /**
     * 获取后台内容审核列表
     * @param page 页码
     * @param size 每页数量
     * @param type 内容类型
     * @param status 内容状态
     * @param keyword 搜索关键字
     * @return Object 分页内容列表
     */
    Object getContents(Integer page, Integer size, PostType type, ContentStatus status, String keyword);

    /**
     * 修改内容状态
     * @param contentId 内容ID
     * @param status 内容状态
     */
    void updateContentStatus(Long contentId, ContentStatus status);
    
    /**
     * 删除任意内容
     * @param contentId 内容ID
     */
    void deleteContent(Long contentId);
    
    /**
     * 获取系统统计
     * @return Object 系统统计数据
     */
    Object getStatistics();

    /**
     * 获取后台文件资源列表
     * @param page 页码
     * @param size 每页数量
     * @param mediaType 媒体类型
     * @param keyword 搜索关键字
     * @return Object 分页文件资源列表
     */
    Object getFiles(Integer page, Integer size, MediaType mediaType, String keyword);

    /**
     * 删除媒体资源
     * @param pmid 媒体资源ID
     */
    void deleteFile(Long pmid);

    /**
     * 获取系统设置
     * @return Map<String, Object> 设置值
     */
    Map<String, Object> getSettings();

    /**
     * 更新系统设置
     * @param settings 设置值
     * @return Map<String, Object> 更新后的设置值
     */
    Map<String, Object> updateSettings(Map<String, Object> settings);

    /**
     * 获取全量AI审计聚合列表
     * @param page 页码
     * @param size 每页数量
     * @param keyword 搜索关键字
     * @return Object 分页AI审计项列表
     */
    Object getAiAuditItems(Integer page, Integer size, String keyword);

    /**
     * 获取全量AI会话审计列表
     * @param page 页码
     * @param size 每页数量
     * @param keyword 搜索关键字
     * @return Object 分页AI会话列表
     */
    Object getAiConversations(Integer page, Integer size, String keyword);

    /**
     * 获取AI会话消息详情
     * @param conversationId 会话ID
     * @return Object 会话详情与消息列表
     */
    Object getAiConversationMessages(Long conversationId);

    /**
     * 删除AI会话及其消息
     * @param conversationId 会话ID
     */
    void deleteAiConversation(Long conversationId);

    /**
     * 获取全量AI记忆审计列表
     * @param page 页码
     * @param size 每页数量
     * @param keyword 搜索关键字
     * @return Object 分页AI记忆列表
     */
    Object getAiMemories(Integer page, Integer size, String keyword);

    /**
     * 删除AI记忆
     * @param memoryId 记忆ID
     */
    void deleteAiMemory(Long memoryId);
}
