package dev.campushubbackend.controller;

import dev.campushubbackend.dto.response.ApiResponse;
import dev.campushubbackend.enums.ActivityType;
import dev.campushubbackend.enums.ApplyStatus;
import dev.campushubbackend.enums.Campus;
import dev.campushubbackend.enums.ContentStatus;
import dev.campushubbackend.enums.MediaType;
import dev.campushubbackend.enums.OrderStatus;
import dev.campushubbackend.enums.PostType;
import dev.campushubbackend.enums.UserStatus;
import dev.campushubbackend.enums.UserType;
import dev.campushubbackend.service.AdminService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 管理员功能相关接口
 */
@RestController
@RequestMapping("/api/v1/admin")
public class AdminController extends BaseController {
    
    private final AdminService adminService;
    
    @Autowired
    public AdminController(AdminService adminService) {
        this.adminService = adminService;
    }
    
    /**
     * 获取用户列表（管理员）
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param userType 用户类型
     * @return ApiResponse<Object>
     */
    @GetMapping("/users")
    public ApiResponse<Object> getUsers(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) UserType userType,
            @RequestParam(required = false) UserStatus userStatus,
            @RequestParam(required = false) String keyword) {
        Object result = adminService.getUsers(page, size, userType, userStatus, keyword);
        return success(result);
    }

    /**
     * 获取后台操作日志
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param moduleName 模块名
     * @param action 操作动作
     * @param keyword 搜索关键字
     * @return ApiResponse<Object>
     */
    @GetMapping("/audit-logs")
    public ApiResponse<Object> getAuditLogs(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String moduleName,
            @RequestParam(required = false) String action,
            @RequestParam(required = false) String keyword) {
        Object result = adminService.getAuditLogs(page, size, moduleName, action, keyword);
        return success(result);
    }
    
    /**
     * 修改用户权限
     * @param userId 用户ID
     * @param userType 用户类型
     * @return ApiResponse<Void>
     */
    @PutMapping("/users/{userId}/type")
    public ApiResponse<Void> updateUserType(
            @PathVariable Long userId,
            @RequestParam UserType userType) {
        adminService.updateUserType(userId, userType);
        return success("修改成功", null);
    }

    /**
     * 修改用户状态
     * @param userId 用户ID
     * @param userStatus 用户状态
     * @return ApiResponse<Void>
     */
    @PutMapping("/users/{userId}/status")
    public ApiResponse<Void> updateUserStatus(
            @PathVariable Long userId,
            @RequestParam UserStatus userStatus) {
        adminService.updateUserStatus(userId, userStatus);
        return success("修改成功", null);
    }

    /**
     * 获取后台订单列表
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param status 订单状态
     * @param activityType 活动类型
     * @param campus 校区
     * @param keyword 搜索关键字
     * @return ApiResponse<Object>
     */
    @GetMapping("/orders")
    public ApiResponse<Object> getOrders(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) OrderStatus status,
            @RequestParam(required = false) ActivityType activityType,
            @RequestParam(required = false) Campus campus,
            @RequestParam(required = false) String keyword) {
        Object result = adminService.getOrders(page, size, status, activityType, campus, keyword);
        return success(result);
    }
    
    /**
     * 管理订单
     * @param orderId 订单ID
     * @param status 订单状态
     * @return ApiResponse<Void>
     */
    @PutMapping("/orders/{orderId}")
    public ApiResponse<Void> manageOrder(
            @PathVariable Long orderId,
            @RequestParam OrderStatus status) {
        adminService.manageOrder(orderId, status);
        return success("修改成功", null);
    }

    /**
     * 获取订单申请审核列表
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param status 申请状态
     * @param keyword 搜索关键字
     * @return ApiResponse<Object>
     */
    @GetMapping("/order-applications")
    public ApiResponse<Object> getOrderApplications(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) ApplyStatus status,
            @RequestParam(required = false) String keyword) {
        Object result = adminService.getOrderApplications(page, size, status, keyword);
        return success(result);
    }

    /**
     * 审核订单申请
     * @param applyId 申请ID
     * @param status 审核状态
     * @return ApiResponse<Void>
     */
    @PutMapping("/order-applications/{applyId}")
    public ApiResponse<Void> auditOrderApplication(
            @PathVariable Long applyId,
            @RequestParam ApplyStatus status) {
        adminService.auditOrderApplication(applyId, status);
        return success("审核成功", null);
    }

    /**
     * 获取内容审核列表
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param type 内容类型
     * @param status 内容状态
     * @param keyword 搜索关键字
     * @return ApiResponse<Object>
     */
    @GetMapping("/contents")
    public ApiResponse<Object> getContents(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) PostType type,
            @RequestParam(required = false) ContentStatus status,
            @RequestParam(required = false) String keyword) {
        Object result = adminService.getContents(page, size, type, status, keyword);
        return success(result);
    }

    /**
     * 修改内容状态
     * @param contentId 内容ID
     * @param status 内容状态
     * @return ApiResponse<Void>
     */
    @PutMapping("/contents/{contentId}/status")
    public ApiResponse<Void> updateContentStatus(
            @PathVariable Long contentId,
            @RequestParam ContentStatus status) {
        adminService.updateContentStatus(contentId, status);
        return success("修改成功", null);
    }
    
    /**
     * 删除任意内容
     * @param contentId 内容ID
     * @return ApiResponse<Void>
     */
    @DeleteMapping("/contents/{contentId}")
    public ApiResponse<Void> deleteContent(@PathVariable Long contentId) {
        adminService.deleteContent(contentId);
        return success("删除成功", null);
    }
    
    /**
     * 获取系统统计
     * @return ApiResponse<Object>
     */
    @GetMapping("/statistics")
    public ApiResponse<Object> getStatistics() {
        Object statistics = adminService.getStatistics();
        return success(statistics);
    }

    /**
     * 获取文件资源列表
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param mediaType 媒体类型
     * @param keyword 搜索关键字
     * @return ApiResponse<Object>
     */
    @GetMapping("/files")
    public ApiResponse<Object> getFiles(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) MediaType mediaType,
            @RequestParam(required = false) String keyword) {
        Object result = adminService.getFiles(page, size, mediaType, keyword);
        return success(result);
    }

    /**
     * 删除文件资源
     * @param pmid 媒体资源ID
     * @return ApiResponse<Void>
     */
    @DeleteMapping("/files/{pmid}")
    public ApiResponse<Void> deleteFile(@PathVariable Long pmid) {
        adminService.deleteFile(pmid);
        return success("删除成功", null);
    }

    /**
     * 获取系统设置
     * @return ApiResponse<Map<String, Object>>
     */
    @GetMapping("/settings")
    public ApiResponse<Map<String, Object>> getSettings() {
        return success(adminService.getSettings());
    }

    /**
     * 更新系统设置
     * @param settings 设置项
     * @return ApiResponse<Map<String, Object>>
     */
    @PutMapping("/settings")
    public ApiResponse<Map<String, Object>> updateSettings(@RequestBody Map<String, Object> settings) {
        return success("保存成功", adminService.updateSettings(settings));
    }

    /**
     * 获取全量AI审计列表
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param keyword 搜索关键字
     * @return ApiResponse<Object>
     */
    @GetMapping("/ai/audit")
    public ApiResponse<Object> getAiAuditItems(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String keyword) {
        return success(adminService.getAiAuditItems(page, size, keyword));
    }

    /**
     * 获取全量AI会话审计列表
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param keyword 搜索关键字
     * @return ApiResponse<Object>
     */
    @GetMapping("/ai/conversations")
    public ApiResponse<Object> getAiConversations(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String keyword) {
        return success(adminService.getAiConversations(page, size, keyword));
    }

    /**
     * 获取AI会话消息详情
     * @param cid 会话ID
     * @return ApiResponse<Object>
     */
    @GetMapping("/ai/conversations/{cid}/messages")
    public ApiResponse<Object> getAiConversationMessages(@PathVariable Long cid) {
        return success(adminService.getAiConversationMessages(cid));
    }

    /**
     * 删除AI会话及其消息
     * @param cid 会话ID
     * @return ApiResponse<Void>
     */
    @DeleteMapping("/ai/conversations/{cid}")
    public ApiResponse<Void> deleteAiConversation(@PathVariable Long cid) {
        adminService.deleteAiConversation(cid);
        return success("删除成功", null);
    }

    /**
     * 获取全量AI记忆审计列表
     * @param page 页码，默认1
     * @param size 每页数量，默认20
     * @param keyword 搜索关键字
     * @return ApiResponse<Object>
     */
    @GetMapping("/ai/memories")
    public ApiResponse<Object> getAiMemories(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String keyword) {
        return success(adminService.getAiMemories(page, size, keyword));
    }

    /**
     * 删除AI记忆
     * @param memId 记忆ID
     * @return ApiResponse<Void>
     */
    @DeleteMapping("/ai/memories/{memId}")
    public ApiResponse<Void> deleteAiMemory(@PathVariable Long memId) {
        adminService.deleteAiMemory(memId);
        return success("删除成功", null);
    }
}
