package dev.campushubbackend.service.impl;

import dev.campushubbackend.dto.response.PageResponse;
import dev.campushubbackend.entity.AdminAuditLog;
import dev.campushubbackend.entity.AiConversation;
import dev.campushubbackend.entity.AiMemory;
import dev.campushubbackend.entity.AiMessage;
import dev.campushubbackend.entity.Order;
import dev.campushubbackend.entity.OrderApply;
import dev.campushubbackend.entity.Post;
import dev.campushubbackend.entity.PostLike;
import dev.campushubbackend.entity.PostMedia;
import dev.campushubbackend.entity.User;
import dev.campushubbackend.enums.ActivityType;
import dev.campushubbackend.enums.ApplyStatus;
import dev.campushubbackend.enums.Campus;
import dev.campushubbackend.enums.ContentStatus;
import dev.campushubbackend.enums.MediaType;
import dev.campushubbackend.enums.OrderStatus;
import dev.campushubbackend.enums.PostType;
import dev.campushubbackend.enums.UserStatus;
import dev.campushubbackend.enums.UserType;
import dev.campushubbackend.exception.ApplicationNotExistException;
import dev.campushubbackend.exception.ContentNotExistException;
import dev.campushubbackend.exception.OrderNotExistException;
import dev.campushubbackend.exception.OrderFullException;
import dev.campushubbackend.exception.ParamValidationFailedException;
import dev.campushubbackend.exception.UserNotExistException;
import dev.campushubbackend.repository.AdminAuditLogRepository;
import dev.campushubbackend.repository.AiConversationRepository;
import dev.campushubbackend.repository.AiMemoryRepository;
import dev.campushubbackend.repository.AiMessageRepository;
import dev.campushubbackend.repository.OrderApplyRepository;
import dev.campushubbackend.repository.OrderRepository;
import dev.campushubbackend.repository.PostLikeRepository;
import dev.campushubbackend.repository.PostMediaRepository;
import dev.campushubbackend.repository.PostRepository;
import dev.campushubbackend.repository.UserRepository;
import dev.campushubbackend.service.AdminService;
import dev.campushubbackend.service.FileService;
import dev.campushubbackend.service.SystemSettingService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.request.RequestAttributes;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AdminServiceImpl implements AdminService {

    private static final int DEFAULT_PAGE_SIZE = 20;
    private static final int MAX_PAGE_SIZE = 100;

    private final UserRepository userRepository;
    private final OrderRepository orderRepository;
    private final OrderApplyRepository orderApplyRepository;
    private final PostRepository postRepository;
    private final PostLikeRepository postLikeRepository;
    private final PostMediaRepository postMediaRepository;
    private final AdminAuditLogRepository adminAuditLogRepository;
    private final AiConversationRepository aiConversationRepository;
    private final AiMemoryRepository aiMemoryRepository;
    private final AiMessageRepository aiMessageRepository;
    private final FileService fileService;
    private final SystemSettingService systemSettingService;

    @Value("${file.upload-dir:uploads}")
    private String baseUploadDir;

    @Override
    public Object getUsers(Integer page, Integer size, UserType userType, UserStatus userStatus, String keyword) {
        log.info("管理员获取用户列表: page={}, size={}, userType={}, userStatus={}, keyword={}",
                page, size, userType, userStatus, keyword);

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<User> users = userRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"))
                .stream()
                .filter(user -> userType == null || userType.equals(user.getUserType()))
                .filter(user -> userStatus == null || userStatus.equals(user.getUserStatus()))
                .filter(user -> matchesUserKeyword(user, normalizedKeyword))
                .collect(Collectors.toList());

        int start = pageStart(safePage, safeSize, users.size());
        int end = pageEnd(start, safeSize, users.size());
        List<Map<String, Object>> resultList = users.subList(start, end)
                .stream()
                .map(this::convertToUserInfo)
                .collect(Collectors.toList());

        return new PageResponse<>(
                resultList,
                (long) users.size(),
                safePage,
                safeSize
        );
    }

    @Override
    @Transactional(readOnly = true)
    public Object getAuditLogs(Integer page, Integer size, String moduleName, String action, String keyword) {
        log.info("管理员获取操作日志: page={}, size={}, moduleName={}, action={}, keyword={}",
                page, size, moduleName, action, keyword);

        String normalizedModule = moduleName == null ? "" : moduleName.trim();
        String normalizedAction = action == null ? "" : action.trim();
        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<AdminAuditLog> auditLogs = adminAuditLogRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"))
                .stream()
                .filter(item -> normalizedModule.isBlank() || normalizedModule.equals(item.getModuleName()))
                .filter(item -> normalizedAction.isBlank() || normalizedAction.equals(item.getAction()))
                .filter(item -> matchesAuditLogKeyword(item, normalizedKeyword))
                .collect(Collectors.toList());

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        int start = pageStart(safePage, safeSize, auditLogs.size());
        int end = pageEnd(start, safeSize, auditLogs.size());

        List<Map<String, Object>> resultList = auditLogs.subList(start, end)
                .stream()
                .map(this::convertToAuditLogInfo)
                .collect(Collectors.toList());

        return new PageResponse<>(resultList, (long) auditLogs.size(), safePage, safeSize);
    }

    @Override
    @Transactional
    public void updateUserType(Long userId, UserType userType) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotExistException("被修改的用户不存在: userId=" + userId));

        UserType oldType = user.getUserType();
        if (UserType.ADMIN.equals(oldType) && !UserType.ADMIN.equals(userType)) {
            if (isCurrentOperator(userId)) {
                throw new ParamValidationFailedException("不能取消自己的管理员权限");
            }
            if (countAdmins() <= 1) {
                throw new ParamValidationFailedException("至少需要保留一个管理员账号");
            }
        }

        user.setUserType(userType);
        log.info("修改用户权限: userId={}, userType={}", userId, userType);
        userRepository.save(user);
        logAdminAction(
                "用户管理",
                "USER_TYPE_UPDATE",
                "USER",
                userId,
                "用户 " + user.getEmail() + " 角色由 " + oldType + " 调整为 " + userType
        );
    }

    @Override
    @Transactional
    public void updateUserStatus(Long userId, UserStatus userStatus) {
        if (UserStatus.REGISTERING.equals(userStatus)) {
            throw new ParamValidationFailedException("不允许将用户状态修改为注册中: userId=" + userId);
        }

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotExistException("被修改的用户不存在: userId=" + userId));

        UserStatus oldStatus = user.getUserStatus();
        if (UserStatus.BANNED.equals(userStatus)) {
            if (isCurrentOperator(userId)) {
                throw new ParamValidationFailedException("不能封禁自己的管理员账号");
            }
            if (UserType.ADMIN.equals(user.getUserType())
                    && !UserStatus.BANNED.equals(oldStatus)
                    && countAvailableAdmins() <= 1) {
                throw new ParamValidationFailedException("至少需要保留一个可用管理员账号");
            }
        }

        user.setUserStatus(userStatus);
        log.info("修改用户状态: userId={}, userStatus={}", userId, userStatus);
        userRepository.save(user);
        logAdminAction(
                "用户管理",
                "USER_STATUS_UPDATE",
                "USER",
                userId,
                "用户 " + user.getEmail() + " 状态由 " + oldStatus + " 调整为 " + userStatus
        );
    }

    @Override
    @Transactional(readOnly = true)
    public Object getOrders(Integer page, Integer size, OrderStatus status, ActivityType activityType, Campus campus, String keyword) {
        log.info("管理员获取订单列表: page={}, size={}, status={}, activityType={}, campus={}, keyword={}",
                page, size, status, activityType, campus, keyword);

        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<Order> orders = orderRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"))
                .stream()
                .filter(order -> status == null || status.equals(order.getStatus()))
                .filter(order -> activityType == null || activityType.equals(order.getActivityType()))
                .filter(order -> campus == null || campus.equals(order.getCampus()))
                .filter(order -> matchesOrderKeyword(order, normalizedKeyword))
                .collect(Collectors.toList());

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        int start = pageStart(safePage, safeSize, orders.size());
        int end = pageEnd(start, safeSize, orders.size());

        List<Map<String, Object>> resultList = orders.subList(start, end)
                .stream()
                .map(this::convertToAdminOrderInfo)
                .collect(Collectors.toList());

        return new PageResponse<>(resultList, (long) orders.size(), safePage, safeSize);
    }

    @Override
    @Transactional
    public void manageOrder(Long orderId, OrderStatus status) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new OrderNotExistException("被管理的订单不存在: orderId=" + orderId));

        OrderStatus oldStatus = order.getStatus();
        order.setStatus(status);
        order.setUpdatedAt(LocalDateTime.now());
        log.info("管理订单: orderId={}, status={}", orderId, status);
        orderRepository.save(order);
        logAdminAction(
                "活动订单",
                "ORDER_STATUS_UPDATE",
                "ORDER",
                orderId,
                "订单状态由 " + oldStatus + " 调整为 " + status + "，活动类型 " + order.getActivityType()
        );
    }

    @Override
    @Transactional(readOnly = true)
    public Object getOrderApplications(Integer page, Integer size, ApplyStatus status, String keyword) {
        log.info("管理员获取订单申请审核列表: page={}, size={}, status={}, keyword={}", page, size, status, keyword);

        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<OrderApply> applications = orderApplyRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"))
                .stream()
                .filter(apply -> status == null || status.equals(apply.getStatus()))
                .filter(apply -> matchesOrderApplicationKeyword(apply, normalizedKeyword))
                .collect(Collectors.toList());

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        int start = pageStart(safePage, safeSize, applications.size());
        int end = pageEnd(start, safeSize, applications.size());

        List<Map<String, Object>> resultList = applications.subList(start, end)
                .stream()
                .map(this::convertToOrderApplicationInfo)
                .collect(Collectors.toList());

        return new PageResponse<>(resultList, (long) applications.size(), safePage, safeSize);
    }

    @Override
    @Transactional
    public void auditOrderApplication(Long applyId, ApplyStatus status) {
        if (status != ApplyStatus.APPROVED && status != ApplyStatus.REJECTED) {
            throw new ParamValidationFailedException("后台仅支持将申请审核为通过或拒绝: applyId=" + applyId);
        }

        OrderApply orderApply = orderApplyRepository.findById(applyId)
                .orElseThrow(() -> new ApplicationNotExistException("申请记录不存在: applyId=" + applyId));

        if (orderApply.getStatus() == ApplyStatus.CANCELLED_APPLY) {
            throw new ParamValidationFailedException("已撤销的申请不能审核: applyId=" + applyId);
        }

        Order order = orderApply.getOrder();
        ApplyStatus oldStatus = orderApply.getStatus();
        boolean wasApproved = orderApply.getStatus() == ApplyStatus.APPROVED;
        boolean willApprove = status == ApplyStatus.APPROVED;

        if (!wasApproved && willApprove) {
            byte currentPeople = order.getCurrentPeople();
            if (currentPeople >= order.getMaxPeople()) {
                throw new OrderFullException("订单已满: orderId=" + order.getOid());
            }
            order.setCurrentPeople((byte) (currentPeople + 1));
        } else if (wasApproved && !willApprove) {
            order.setCurrentPeople((byte) Math.max(0, order.getCurrentPeople() - 1));
        }

        order.setUpdatedAt(LocalDateTime.now());
        orderApply.setStatus(status);
        orderRepository.save(order);
        orderApplyRepository.save(orderApply);
        log.info("管理员审核订单申请: applyId={}, status={}", applyId, status);
        logAdminAction(
                "活动订单",
                "ORDER_APPLICATION_AUDIT",
                "ORDER_APPLY",
                applyId,
                "申请状态由 " + oldStatus + " 调整为 " + status + "，关联订单 " + order.getOid()
        );
    }

    @Override
    @Transactional(readOnly = true)
    public Object getContents(Integer page, Integer size, PostType type, ContentStatus status, String keyword) {
        log.info("管理员获取内容审核列表: page={}, size={}, type={}, status={}, keyword={}",
                page, size, type, status, keyword);

        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<Post> posts = postRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"))
                .stream()
                .filter(post -> type == null || type.equals(post.getType()))
                .filter(post -> status == null || status.equals(post.getStatus()))
                .filter(post -> matchesContentKeyword(post, normalizedKeyword))
                .collect(Collectors.toList());

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        int start = pageStart(safePage, safeSize, posts.size());
        int end = pageEnd(start, safeSize, posts.size());

        List<Map<String, Object>> resultList = posts.subList(start, end)
                .stream()
                .map(this::convertToAdminContentInfo)
                .collect(Collectors.toList());

        return new PageResponse<>(resultList, (long) posts.size(), safePage, safeSize);
    }

    @Override
    @Transactional
    public void updateContentStatus(Long contentId, ContentStatus status) {
        Post post = postRepository.findById(contentId)
                .orElseThrow(() -> new ContentNotExistException("内容不存在: contentId=" + contentId));

        ContentStatus oldStatus = post.getStatus();
        post.setStatus(status);
        post.setUpdatedAt(LocalDateTime.now());
        postRepository.save(post);
        log.info("管理员修改内容状态: contentId={}, status={}", contentId, status);
        logAdminAction(
                post.getType() == PostType.COMMENT ? "评论审核" : "动态内容",
                "CONTENT_STATUS_UPDATE",
                "POST",
                contentId,
                "内容状态由 " + oldStatus + " 调整为 " + status + "，内容：" + preview(post.getContent(), 60)
        );
    }

    @Override
    @Transactional
    public void deleteContent(Long contentId) {
        Post post = postRepository.findById(contentId)
                .orElseThrow(() -> new ContentNotExistException("动态不存在: contentId=" + contentId));

        post.setStatus(ContentStatus.DELETED);
        post.setUpdatedAt(LocalDateTime.now());
        log.info("管理员删除内容: contentId={}", contentId);
        postRepository.save(post);
        logAdminAction(
                post.getType() == PostType.COMMENT ? "评论审核" : "动态内容",
                "CONTENT_DELETE",
                "POST",
                contentId,
                "删除内容：" + preview(post.getContent(), 80)
        );
    }

    @Override
    public Object getStatistics() {
        log.info("获取系统统计");

        Map<String, Object> statistics = new HashMap<>();

        List<User> users = userRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"));
        long totalUsers = users.size();
        long adminCount = users.stream().filter(user -> user.getUserType() == UserType.ADMIN).count();
        long commonUserCount = totalUsers - adminCount;
        Map<String, Long> userStatusCounts = countByEnum(UserStatus.class, users, User::getUserStatus);
        Map<String, Long> userTypeCounts = countByEnum(UserType.class, users, User::getUserType);
        LocalDateTime todayStart = LocalDate.now().atStartOfDay();
        long todayActiveUsers = users.stream()
                .filter(user -> user.getLastLoginAt() != null && !user.getLastLoginAt().isBefore(todayStart))
                .count();

        statistics.put("userCount", totalUsers);
        statistics.put("adminCount", adminCount);
        statistics.put("commonUserCount", commonUserCount);
        statistics.put("todayActiveUsers", todayActiveUsers);
        statistics.put("onlineUserCount", userStatusCounts.get("ONLINE"));
        statistics.put("bannedUserCount", userStatusCounts.get("BANNED"));
        statistics.put("userStatusCounts", userStatusCounts);
        statistics.put("userTypeCounts", userTypeCounts);

        List<Order> orders = orderRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"));
        Map<String, Long> orderStatusCounts = countByEnum(OrderStatus.class, orders, Order::getStatus);

        statistics.put("orderCount", (long) orders.size());
        statistics.put("pendingOrderCount", orderStatusCounts.get("PENDING"));
        statistics.put("inProgressOrderCount", orderStatusCounts.get("IN_PROGRESS"));
        statistics.put("completedOrderCount", orderStatusCounts.get("COMPLETED"));
        statistics.put("cancelledOrderCount", orderStatusCounts.get("CANCELLED"));
        statistics.put("expiredOrderCount", orderStatusCounts.get("EXPIRED"));
        statistics.put("orderStatusCounts", orderStatusCounts);

        List<OrderApply> applications = orderApplyRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"));
        Map<String, Long> applicationStatusCounts = countByEnum(ApplyStatus.class, applications, OrderApply::getStatus);
        statistics.put("applicationCount", (long) applications.size());
        statistics.put("pendingApplicationCount", applicationStatusCounts.get("PENDING_REVIEW"));
        statistics.put("approvedApplicationCount", applicationStatusCounts.get("APPROVED"));
        statistics.put("rejectedApplicationCount", applicationStatusCounts.get("REJECTED"));
        statistics.put("cancelledApplicationCount", applicationStatusCounts.get("CANCELLED_APPLY"));
        statistics.put("applicationStatusCounts", applicationStatusCounts);

        List<Post> allPosts = postRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"));
        Map<String, Long> contentStatusCounts = countByEnum(ContentStatus.class, allPosts, Post::getStatus);
        Map<String, Long> postTypeCounts = countByEnum(PostType.class, allPosts, Post::getType);
        long activePostCount = allPosts.stream()
                .filter(post -> post.getType() == PostType.POST && post.getStatus() == ContentStatus.NORMAL)
                .count();
        long activeCommentCount = allPosts.stream()
                .filter(post -> post.getType() == PostType.COMMENT && post.getStatus() == ContentStatus.NORMAL)
                .count();
        long pendingPostCount = allPosts.stream()
                .filter(post -> post.getType() == PostType.POST && post.getStatus() == ContentStatus.PENDING)
                .count();
        long pendingCommentCount = allPosts.stream()
                .filter(post -> post.getType() == PostType.COMMENT && post.getStatus() == ContentStatus.PENDING)
                .count();

        statistics.put("contentCount", (long) allPosts.size());
        statistics.put("postCount", activePostCount);
        statistics.put("commentCount", activeCommentCount);
        statistics.put("pendingPostCount", pendingPostCount);
        statistics.put("pendingCommentCount", pendingCommentCount);
        statistics.put("pendingContentCount", contentStatusCounts.get("PENDING"));
        statistics.put("rejectedContentCount", contentStatusCounts.get("REJECTED"));
        statistics.put("deletedContentCount", contentStatusCounts.get("DELETED"));
        statistics.put("contentStatusCounts", contentStatusCounts);
        statistics.put("postTypeCounts", postTypeCounts);

        List<PostMedia> mediaList = postMediaRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"));
        Map<String, Long> mediaTypeCounts = countByEnum(MediaType.class, mediaList, PostMedia::getMediaType);
        statistics.put("fileCount", (long) mediaList.size());
        statistics.put("imageFileCount", mediaTypeCounts.get("IMAGE"));
        statistics.put("videoFileCount", mediaTypeCounts.get("VIDEO"));
        statistics.put("mediaTypeCounts", mediaTypeCounts);

        long aiConversationCount = aiConversationRepository.count();
        long aiMemoryCount = aiMemoryRepository.count();
        long aiMessageCount = aiMessageRepository.count();
        statistics.put("aiConversationCount", aiConversationCount);
        statistics.put("aiMemoryCount", aiMemoryCount);
        statistics.put("aiMessageCount", aiMessageCount);

        return statistics;
    }

    @Override
    @Transactional(readOnly = true)
    public Object getFiles(Integer page, Integer size, MediaType mediaType, String keyword) {
        log.info("管理员获取文件资源: page={}, size={}, mediaType={}, keyword={}", page, size, mediaType, keyword);

        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<PostMedia> mediaList = postMediaRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt"))
                .stream()
                .filter(media -> mediaType == null || mediaType.equals(media.getMediaType()))
                .filter(media -> matchesFileKeyword(media, normalizedKeyword))
                .collect(Collectors.toList());

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        int start = pageStart(safePage, safeSize, mediaList.size());
        int end = pageEnd(start, safeSize, mediaList.size());

        List<Map<String, Object>> resultList = mediaList.subList(start, end)
                .stream()
                .map(this::convertToFileInfo)
                .collect(Collectors.toList());

        return new PageResponse<>(resultList, (long) mediaList.size(), safePage, safeSize);
    }

    @Override
    @Transactional
    public void deleteFile(Long pmid) {
        PostMedia media = postMediaRepository.findById(pmid)
                .orElseThrow(() -> new ContentNotExistException("文件资源不存在: pmid=" + pmid));

        try {
            fileService.deleteFile(media.getUrl());
        } catch (RuntimeException ex) {
            log.warn("删除物理文件失败，将继续删除媒体记录: pmid={}, url={}, reason={}",
                    pmid, media.getUrl(), ex.getMessage());
        }

        postMediaRepository.delete(media);
        log.info("管理员删除文件资源: pmid={}", pmid);
        logAdminAction(
                "文件资源",
                "FILE_DELETE",
                "POST_MEDIA",
                pmid,
                "删除文件资源：" + media.getUrl()
        );
    }

    @Override
    @Transactional(readOnly = true)
    public Map<String, Object> getSettings() {
        return systemSettingService.getSettings();
    }

    @Override
    @Transactional
    public Map<String, Object> updateSettings(Map<String, Object> settings) {
        if (settings == null) {
            settings = Map.of();
        }
        Map<String, Object> updatedSettings = systemSettingService.updateSettings(settings);

        logAdminAction(
                "系统设置",
                "SETTINGS_UPDATE",
                "SYSTEM_SETTING",
                null,
                "更新设置项：" + settings.keySet()
                        .stream()
                        .map(key -> settingLabels().getOrDefault(key, key))
                        .collect(Collectors.joining(", "))
        );
        return updatedSettings;
    }

    @Override
    @Transactional(readOnly = true)
    public Object getAiAuditItems(Integer page, Integer size, String keyword) {
        log.info("管理员获取AI审计聚合列表: page={}, size={}, keyword={}", page, size, keyword);

        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<Map<String, Object>> aiItems = new ArrayList<>();

        aiItems.addAll(aiConversationRepository.findAll(Sort.by(Sort.Direction.DESC, "updatedAt"))
                .stream()
                .filter(conversation -> matchesAiConversationKeyword(conversation, normalizedKeyword))
                .map(this::convertToAiConversationInfo)
                .collect(Collectors.toList()));
        aiItems.addAll(aiMemoryRepository.findAll(Sort.by(Sort.Direction.DESC, "updatedAt"))
                .stream()
                .filter(memory -> matchesAiMemoryKeyword(memory, normalizedKeyword))
                .map(this::convertToAiMemoryInfo)
                .collect(Collectors.toList()));

        aiItems.sort((left, right) -> aiAuditTime(right).compareTo(aiAuditTime(left)));

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        int start = pageStart(safePage, safeSize, aiItems.size());
        int end = pageEnd(start, safeSize, aiItems.size());

        return new PageResponse<>(
                new ArrayList<>(aiItems.subList(start, end)),
                (long) aiItems.size(),
                safePage,
                safeSize
        );
    }

    @Override
    @Transactional(readOnly = true)
    public Object getAiConversations(Integer page, Integer size, String keyword) {
        log.info("管理员获取AI会话审计列表: page={}, size={}, keyword={}", page, size, keyword);

        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<AiConversation> conversations = aiConversationRepository.findAll(Sort.by(Sort.Direction.DESC, "updatedAt"))
                .stream()
                .filter(conversation -> matchesAiConversationKeyword(conversation, normalizedKeyword))
                .collect(Collectors.toList());

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        int start = pageStart(safePage, safeSize, conversations.size());
        int end = pageEnd(start, safeSize, conversations.size());

        List<Map<String, Object>> resultList = conversations.subList(start, end)
                .stream()
                .map(this::convertToAiConversationInfo)
                .collect(Collectors.toList());

        return new PageResponse<>(resultList, (long) conversations.size(), safePage, safeSize);
    }

    @Override
    @Transactional(readOnly = true)
    public Object getAiConversationMessages(Long conversationId) {
        log.info("管理员获取AI会话消息详情: conversationId={}", conversationId);

        AiConversation conversation = findAiConversationOrThrow(conversationId);
        List<Map<String, Object>> messages = aiMessageRepository.findByConversationOrderByCreatedAtAsc(conversation)
                .stream()
                .map(this::convertToAiMessageInfo)
                .collect(Collectors.toList());

        Map<String, Object> result = new HashMap<>();
        result.put("conversation", convertToAiConversationInfo(conversation));
        result.put("messages", messages);
        return result;
    }

    @Override
    @Transactional
    public void deleteAiConversation(Long conversationId) {
        log.info("管理员删除AI会话: conversationId={}", conversationId);

        AiConversation conversation = findAiConversationOrThrow(conversationId);
        int messageCount = aiMessageRepository.findByConversationOrderByCreatedAtAsc(conversation).size();
        aiMessageRepository.deleteByConversation(conversation);
        aiConversationRepository.delete(conversation);
        logAdminAction(
                "AI会话",
                "AI_CONVERSATION_DELETE",
                "AI_CONVERSATION",
                conversationId,
                "删除会话「" + conversation.getTitle() + "」，消息数 " + messageCount
        );
    }

    @Override
    @Transactional(readOnly = true)
    public Object getAiMemories(Integer page, Integer size, String keyword) {
        log.info("管理员获取AI记忆审计列表: page={}, size={}, keyword={}", page, size, keyword);

        String normalizedKeyword = keyword == null ? "" : keyword.trim().toLowerCase();
        List<AiMemory> memories = aiMemoryRepository.findAll(Sort.by(Sort.Direction.DESC, "updatedAt"))
                .stream()
                .filter(memory -> matchesAiMemoryKeyword(memory, normalizedKeyword))
                .collect(Collectors.toList());

        int safePage = normalizePage(page);
        int safeSize = normalizeSize(size);
        int start = pageStart(safePage, safeSize, memories.size());
        int end = pageEnd(start, safeSize, memories.size());

        List<Map<String, Object>> resultList = memories.subList(start, end)
                .stream()
                .map(this::convertToAiMemoryInfo)
                .collect(Collectors.toList());

        return new PageResponse<>(resultList, (long) memories.size(), safePage, safeSize);
    }

    @Override
    @Transactional
    public void deleteAiMemory(Long memoryId) {
        log.info("管理员删除AI记忆: memoryId={}", memoryId);

        if (memoryId == null) {
            throw new ParamValidationFailedException("AI记忆ID不能为空");
        }

        AiMemory memory = aiMemoryRepository.findById(memoryId)
                .orElseThrow(() -> new ParamValidationFailedException("AI记忆不存在: memoryId=" + memoryId));
        aiMemoryRepository.delete(memory);
        logAdminAction(
                "AI会话",
                "AI_MEMORY_DELETE",
                "AI_MEMORY",
                memoryId,
                "删除长期记忆：" + preview(memory.getContent(), 80)
        );
    }

    private AiConversation findAiConversationOrThrow(Long conversationId) {
        if (conversationId == null) {
            throw new ParamValidationFailedException("AI会话ID不能为空");
        }

        return aiConversationRepository.findById(conversationId)
                .orElseThrow(() -> new ParamValidationFailedException("AI会话不存在: conversationId=" + conversationId));
    }

    private Map<String, Object> convertToUserInfo(User user) {
        Map<String, Object> userInfo = new HashMap<>();
        userInfo.put("id", user.getUid());
        userInfo.put("email", user.getEmail());
        userInfo.put("nickname", user.getNickname());
        userInfo.put("avatarUrl", user.getAvatarUrl());
        userInfo.put("userType", user.getUserType());
        userInfo.put("userStatus", user.getUserStatus());
        userInfo.put("createdAt", user.getCreatedAt());
        userInfo.put("lastLoginAt", user.getLastLoginAt());
        return userInfo;
    }

    private <T, E extends Enum<E>> Map<String, Long> countByEnum(
            Class<E> enumType,
            List<T> items,
            Function<T, E> extractor) {
        Map<String, Long> counts = new LinkedHashMap<>();
        for (E value : enumType.getEnumConstants()) {
            counts.put(value.name(), 0L);
        }

        for (T item : items) {
            E value = extractor.apply(item);
            if (value != null) {
                counts.put(value.name(), counts.getOrDefault(value.name(), 0L) + 1);
            }
        }

        return counts;
    }

    private boolean matchesUserKeyword(User user, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }

        StringBuilder searchable = new StringBuilder();
        searchable.append(user.getUid()).append(' ');
        searchable.append(user.getEmail()).append(' ');
        searchable.append(user.getNickname()).append(' ');
        searchable.append(user.getUserType()).append(' ');
        searchable.append(user.getUserStatus());

        return searchable.toString().toLowerCase().contains(keyword);
    }

    private boolean matchesFileKeyword(PostMedia media, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }

        StringBuilder searchable = new StringBuilder();
        searchable.append(media.getUrl()).append(' ');
        searchable.append(media.getMediaType()).append(' ');

        Post post = media.getPost();
        if (post != null) {
            searchable.append(post.getContent()).append(' ');
            User user = post.getUser();
            if (user != null) {
                searchable.append(user.getNickname()).append(' ');
                searchable.append(user.getEmail());
            }
        }

        return searchable.toString().toLowerCase().contains(keyword);
    }

    private boolean matchesAuditLogKeyword(AdminAuditLog auditLog, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }

        StringBuilder searchable = new StringBuilder();
        searchable.append(auditLog.getModuleName()).append(' ');
        searchable.append(auditLog.getAction()).append(' ');
        searchable.append(auditLog.getTargetType()).append(' ');
        searchable.append(auditLog.getTargetId()).append(' ');
        searchable.append(auditLog.getDetail()).append(' ');
        searchable.append(auditLog.getIpAddress()).append(' ');
        User operator = auditLog.getOperator();
        if (operator != null) {
            searchable.append(operator.getNickname()).append(' ');
            searchable.append(operator.getEmail());
        }

        return searchable.toString().toLowerCase().contains(keyword);
    }

    private boolean matchesAiConversationKeyword(AiConversation conversation, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }

        StringBuilder searchable = new StringBuilder();
        searchable.append(conversation.getTitle()).append(' ');
        User user = conversation.getUser();
        if (user != null) {
            searchable.append(user.getNickname()).append(' ');
            searchable.append(user.getEmail());
        }
        return searchable.toString().toLowerCase().contains(keyword);
    }

    private boolean matchesAiMemoryKeyword(AiMemory memory, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }

        StringBuilder searchable = new StringBuilder();
        searchable.append(memory.getCategory()).append(' ');
        searchable.append(memory.getContent()).append(' ');
        searchable.append(memory.getSource()).append(' ');
        User user = memory.getUser();
        if (user != null) {
            searchable.append(user.getNickname()).append(' ');
            searchable.append(user.getEmail());
        }
        return searchable.toString().toLowerCase().contains(keyword);
    }

    private boolean matchesOrderApplicationKeyword(OrderApply apply, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }

        StringBuilder searchable = new StringBuilder();
        searchable.append(apply.getStatus()).append(' ');

        User applicant = apply.getUser();
        if (applicant != null) {
            searchable.append(applicant.getNickname()).append(' ');
            searchable.append(applicant.getEmail()).append(' ');
        }

        Order order = apply.getOrder();
        if (order != null) {
            searchable.append(order.getActivityType()).append(' ');
            searchable.append(activityLabel(order.getActivityType())).append(' ');
            searchable.append(order.getCampus()).append(' ');
            searchable.append(campusLabel(order.getCampus())).append(' ');
            searchable.append(order.getLocation()).append(' ');
            searchable.append(order.getNote()).append(' ');
            User owner = order.getUser();
            if (owner != null) {
                searchable.append(owner.getNickname()).append(' ');
                searchable.append(owner.getEmail());
            }
        }

        return searchable.toString().toLowerCase().contains(keyword);
    }

    private boolean matchesOrderKeyword(Order order, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }

        StringBuilder searchable = new StringBuilder();
        searchable.append(order.getOid()).append(' ');
        searchable.append(order.getActivityType()).append(' ');
        searchable.append(activityLabel(order.getActivityType())).append(' ');
        searchable.append(order.getGenderRequire()).append(' ');
        searchable.append(genderRequireLabel(order.getGenderRequire())).append(' ');
        searchable.append(order.getCampus()).append(' ');
        searchable.append(campusLabel(order.getCampus())).append(' ');
        searchable.append(order.getLocation()).append(' ');
        searchable.append(order.getNote()).append(' ');
        searchable.append(order.getStatus()).append(' ');

        User owner = order.getUser();
        if (owner != null) {
            searchable.append(owner.getNickname()).append(' ');
            searchable.append(owner.getEmail()).append(' ');
            searchable.append(owner.getUid());
        }

        return searchable.toString().toLowerCase().contains(keyword);
    }

    private String activityLabel(ActivityType activityType) {
        if (activityType == null) {
            return "";
        }
        return switch (activityType) {
            case BASKETBALL -> "篮球";
            case BADMINTON -> "羽毛球";
            case MEAL -> "吃饭";
            case STUDY -> "自习";
            case MOVIE -> "看电影";
            case RUNNING -> "跑步";
            case GAME -> "游戏";
            case OTHER -> "其他";
        };
    }

    private String campusLabel(Campus campus) {
        if (campus == null) {
            return "";
        }
        return switch (campus) {
            case LIANGXIANG -> "良乡校区";
            case ZHONGGUANCUN -> "中关村校区";
            case ZHUHAI -> "珠海校区";
            case XISHAN -> "西山校区";
            case OTHER_CAMPUS -> "其他校区";
        };
    }

    private String genderRequireLabel(dev.campushubbackend.enums.GenderRequire genderRequire) {
        if (genderRequire == null) {
            return "";
        }
        return switch (genderRequire) {
            case MALE -> "男";
            case FEMALE -> "女";
            case ANY -> "不限";
        };
    }

    private boolean matchesContentKeyword(Post post, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }

        StringBuilder searchable = new StringBuilder();
        searchable.append(post.getContent()).append(' ');
        searchable.append(post.getType()).append(' ');
        searchable.append(post.getStatus()).append(' ');
        searchable.append(post.getHasMedia()).append(' ');

        User user = post.getUser();
        if (user != null) {
            searchable.append(user.getNickname()).append(' ');
            searchable.append(user.getEmail()).append(' ');
        }

        Post parent = post.getParentPost();
        if (parent != null) {
            searchable.append(parent.getContent()).append(' ');
        }

        Order order = post.getOrder();
        if (order != null) {
            searchable.append(order.getActivityType()).append(' ');
            searchable.append(order.getLocation()).append(' ');
            searchable.append(order.getCampus());
        }

        return searchable.toString().toLowerCase().contains(keyword);
    }

    private Map<String, Object> convertToOrderApplicationInfo(OrderApply apply) {
        Map<String, Object> applyInfo = new HashMap<>();
        applyInfo.put("id", apply.getApid());
        applyInfo.put("applyId", apply.getApid());
        applyInfo.put("status", apply.getStatus());
        applyInfo.put("createdAt", apply.getCreatedAt());
        applyInfo.put("user", convertSimpleUser(apply.getUser()));

        Order order = apply.getOrder();
        if (order != null) {
            Map<String, Object> orderInfo = new HashMap<>();
            orderInfo.put("id", order.getOid());
            orderInfo.put("activityType", order.getActivityType());
            orderInfo.put("campus", order.getCampus());
            orderInfo.put("location", order.getLocation());
            orderInfo.put("startTime", order.getStartTime());
            orderInfo.put("note", preview(order.getNote(), 72));
            orderInfo.put("maxPeople", order.getMaxPeople());
            orderInfo.put("currentPeople", order.getCurrentPeople());
            orderInfo.put("status", order.getStatus());
            orderInfo.put("user", convertSimpleUser(order.getUser()));
            applyInfo.put("order", orderInfo);
        }

        return applyInfo;
    }

    private Map<String, Object> convertToAdminOrderInfo(Order order) {
        Map<String, Object> orderInfo = new HashMap<>();
        orderInfo.put("id", order.getOid());
        orderInfo.put("activityType", order.getActivityType());
        orderInfo.put("genderRequire", order.getGenderRequire());
        orderInfo.put("campus", order.getCampus());
        orderInfo.put("location", order.getLocation());
        orderInfo.put("startTime", order.getStartTime());
        orderInfo.put("note", order.getNote());
        orderInfo.put("maxPeople", order.getMaxPeople());
        orderInfo.put("currentPeople", order.getCurrentPeople());
        orderInfo.put("status", order.getStatus());
        orderInfo.put("createdAt", order.getCreatedAt());
        orderInfo.put("updatedAt", order.getUpdatedAt());
        orderInfo.put("user", convertSimpleUser(order.getUser()));
        return orderInfo;
    }

    private Map<String, Object> convertToAdminContentInfo(Post post) {
        Map<String, Object> contentInfo = new HashMap<>();
        contentInfo.put("id", post.getPid());
        contentInfo.put("type", post.getType());
        contentInfo.put("content", post.getContent());
        contentInfo.put("mediaType", post.getHasMedia());
        contentInfo.put("status", post.getStatus());
        contentInfo.put("createdAt", post.getCreatedAt());
        contentInfo.put("updatedAt", post.getUpdatedAt());
        contentInfo.put("user", convertSimpleUser(post.getUser()));

        Post parent = post.getParentPost();
        if (parent != null) {
            Map<String, Object> parentInfo = new HashMap<>();
            parentInfo.put("id", parent.getPid());
            parentInfo.put("type", parent.getType());
            parentInfo.put("content", preview(parent.getContent(), 72));
            contentInfo.put("parent", parentInfo);
        }

        Order order = post.getOrder();
        if (order != null) {
            Map<String, Object> orderInfo = new HashMap<>();
            orderInfo.put("id", order.getOid());
            orderInfo.put("activityType", order.getActivityType());
            orderInfo.put("campus", order.getCampus());
            orderInfo.put("location", order.getLocation());
            orderInfo.put("startTime", order.getStartTime());
            contentInfo.put("order", orderInfo);
        }

        List<PostLike> likes = postLikeRepository.findByPost(post);
        List<Post> comments = postRepository.findByParentPostAndTypeAndStatusOrderByCreatedAtDesc(
                post, PostType.COMMENT, ContentStatus.NORMAL);
        List<PostMedia> mediaList = postMediaRepository.findByPost(post);

        contentInfo.put("likeCount", likes.size());
        contentInfo.put("commentCount", comments.size());
        contentInfo.put("mediaUrls", mediaList.stream().map(PostMedia::getUrl).collect(Collectors.toList()));

        return contentInfo;
    }

    private Map<String, Object> convertToAuditLogInfo(AdminAuditLog auditLog) {
        Map<String, Object> auditLogInfo = new HashMap<>();
        auditLogInfo.put("id", auditLog.getId());
        auditLogInfo.put("moduleName", auditLog.getModuleName());
        auditLogInfo.put("action", auditLog.getAction());
        auditLogInfo.put("actionLabel", auditActionLabel(auditLog.getAction()));
        auditLogInfo.put("targetType", auditLog.getTargetType());
        auditLogInfo.put("targetId", auditLog.getTargetId());
        auditLogInfo.put("detail", auditLog.getDetail());
        auditLogInfo.put("ipAddress", auditLog.getIpAddress());
        auditLogInfo.put("createdAt", auditLog.getCreatedAt());
        auditLogInfo.put("operator", convertSimpleUser(auditLog.getOperator()));
        return auditLogInfo;
    }

    private String auditActionLabel(String action) {
        Map<String, String> labels = new HashMap<>();
        labels.put("USER_TYPE_UPDATE", "修改角色");
        labels.put("USER_STATUS_UPDATE", "修改状态");
        labels.put("ORDER_STATUS_UPDATE", "订单调度");
        labels.put("ORDER_APPLICATION_AUDIT", "报名审核");
        labels.put("CONTENT_STATUS_UPDATE", "内容状态");
        labels.put("CONTENT_DELETE", "删除内容");
        labels.put("FILE_DELETE", "删除资源");
        labels.put("SETTINGS_UPDATE", "更新设置");
        labels.put("AI_CONVERSATION_DELETE", "删除AI会话");
        labels.put("AI_MEMORY_DELETE", "删除AI记忆");
        return labels.getOrDefault(action, action);
    }

    private Map<String, Object> convertToAiConversationInfo(AiConversation conversation) {
        Map<String, Object> conversationInfo = new HashMap<>();
        conversationInfo.put("id", conversation.getCid());
        conversationInfo.put("cid", conversation.getCid());
        conversationInfo.put("category", "会话");
        conversationInfo.put("title", conversation.getTitle());
        conversationInfo.put("messageCount", aiMessageRepository.findByConversationOrderByCreatedAtAsc(conversation).size());
        conversationInfo.put("createdAt", conversation.getCreatedAt());
        conversationInfo.put("updatedAt", conversation.getUpdatedAt());
        conversationInfo.put("user", convertSimpleUser(conversation.getUser()));
        return conversationInfo;
    }

    private Map<String, Object> convertToAiMessageInfo(AiMessage message) {
        Map<String, Object> messageInfo = new HashMap<>();
        messageInfo.put("id", message.getMid());
        messageInfo.put("mid", message.getMid());
        messageInfo.put("role", message.getRole());
        messageInfo.put("content", message.getContent());
        messageInfo.put("toolName", message.getToolName());
        messageInfo.put("tokenCount", message.getTokenCount());
        messageInfo.put("createdAt", message.getCreatedAt());
        return messageInfo;
    }

    private Map<String, Object> convertToAiMemoryInfo(AiMemory memory) {
        Map<String, Object> memoryInfo = new HashMap<>();
        memoryInfo.put("id", memory.getMemId());
        memoryInfo.put("memId", memory.getMemId());
        memoryInfo.put("category", "记忆");
        memoryInfo.put("memoryCategory", memory.getCategory());
        memoryInfo.put("content", memory.getContent());
        memoryInfo.put("source", memory.getSource());
        memoryInfo.put("createdAt", memory.getCreatedAt());
        memoryInfo.put("updatedAt", memory.getUpdatedAt());
        memoryInfo.put("user", convertSimpleUser(memory.getUser()));
        return memoryInfo;
    }

    private LocalDateTime aiAuditTime(Map<String, Object> item) {
        Object updatedAt = item.get("updatedAt");
        if (updatedAt instanceof LocalDateTime value) {
            return value;
        }

        Object createdAt = item.get("createdAt");
        if (createdAt instanceof LocalDateTime value) {
            return value;
        }

        return LocalDateTime.MIN;
    }

    private Map<String, Object> convertSimpleUser(User user) {
        Map<String, Object> userInfo = new HashMap<>();
        if (user == null) {
            return userInfo;
        }
        userInfo.put("id", user.getUid());
        userInfo.put("nickname", user.getNickname());
        userInfo.put("email", user.getEmail());
        return userInfo;
    }

    private Map<String, Object> convertToFileInfo(PostMedia media) {
        Map<String, Object> fileInfo = new HashMap<>();
        fileInfo.put("id", media.getPmid());
        fileInfo.put("pmid", media.getPmid());
        fileInfo.put("mediaType", media.getMediaType());
        fileInfo.put("url", media.getUrl());
        fileInfo.put("filename", extractFilename(media.getUrl()));
        fileInfo.put("size", resolveFileSize(media.getUrl()));
        fileInfo.put("createdAt", media.getCreatedAt());

        Post post = media.getPost();
        if (post != null) {
            fileInfo.put("postId", post.getPid());
            fileInfo.put("postType", post.getType());
            fileInfo.put("postContent", preview(post.getContent(), 72));

            User user = post.getUser();
            if (user != null) {
                Map<String, Object> userInfo = new HashMap<>();
                userInfo.put("id", user.getUid());
                userInfo.put("nickname", user.getNickname());
                userInfo.put("email", user.getEmail());
                fileInfo.put("user", userInfo);
            }
        }

        return fileInfo;
    }

    private String extractFilename(String url) {
        if (url == null || url.isBlank()) {
            return "-";
        }
        String normalized = url.replace("\\", "/");
        int index = normalized.lastIndexOf('/');
        return index >= 0 ? normalized.substring(index + 1) : normalized;
    }

    private int normalizePage(Integer page) {
        return Math.max(page == null ? 1 : page, 1);
    }

    private int normalizeSize(Integer size) {
        int requestedSize = Math.max(size == null ? DEFAULT_PAGE_SIZE : size, 1);
        return Math.min(requestedSize, MAX_PAGE_SIZE);
    }

    private int pageStart(int safePage, int safeSize, int totalSize) {
        long start = ((long) safePage - 1L) * safeSize;
        return (int) Math.min(start, totalSize);
    }

    private int pageEnd(int start, int safeSize, int totalSize) {
        return Math.min(start + safeSize, totalSize);
    }

    private Long resolveFileSize(String url) {
        try {
            Path filePath = resolveUploadPath(url);
            if (Files.exists(filePath) && Files.isRegularFile(filePath)) {
                return Files.size(filePath);
            }
        } catch (Exception ex) {
            log.debug("读取文件大小失败: url={}, reason={}", url, ex.getMessage());
        }
        return null;
    }

    private Path resolveUploadPath(String fileUrl) {
        String url = fileUrl == null ? "" : fileUrl.trim();
        if (url.startsWith("/")) {
            url = url.substring(1);
        }

        Path cwd = Paths.get("").toAbsolutePath().normalize();
        Path baseUploadPath = Paths.get(baseUploadDir);
        if (!baseUploadPath.isAbsolute()) {
            baseUploadPath = cwd.resolve(baseUploadDir).normalize();
        } else {
            baseUploadPath = baseUploadPath.normalize();
        }

        String normalizedBase = baseUploadPath.getFileName() != null
                ? baseUploadPath.getFileName().toString()
                : baseUploadDir;
        if (url.startsWith(normalizedBase + "/")) {
            url = url.substring(normalizedBase.length() + 1);
        }

        Path resolvedPath = baseUploadPath.resolve(url).normalize();
        if (!resolvedPath.startsWith(baseUploadPath)) {
            throw new IllegalArgumentException("文件路径超出上传目录");
        }
        return resolvedPath;
    }

    private String preview(String text, int maxLength) {
        if (text == null) {
            return "";
        }
        String normalized = text.replaceAll("\\s+", " ").trim();
        if (normalized.length() <= maxLength) {
            return normalized;
        }
        return normalized.substring(0, maxLength) + "...";
    }

    private boolean isCurrentOperator(Long userId) {
        Long operatorId = getCurrentOperatorIdOrNull();
        return operatorId != null && operatorId.equals(userId);
    }

    private long countAdmins() {
        return userRepository.findAll()
                .stream()
                .filter(user -> UserType.ADMIN.equals(user.getUserType()))
                .count();
    }

    private long countAvailableAdmins() {
        return userRepository.findAll()
                .stream()
                .filter(user -> UserType.ADMIN.equals(user.getUserType()))
                .filter(user -> !UserStatus.BANNED.equals(user.getUserStatus()))
                .count();
    }

    private void logAdminAction(String moduleName, String action, String targetType, Long targetId, String detail) {
        try {
            AdminAuditLog auditLog = new AdminAuditLog();
            auditLog.setModuleName(moduleName);
            auditLog.setAction(action);
            auditLog.setTargetType(targetType);
            auditLog.setTargetId(targetId);
            auditLog.setDetail(detail == null || detail.isBlank() ? "-" : detail);
            auditLog.setIpAddress(resolveRequestIpAddress());

            Long operatorId = getCurrentOperatorIdOrNull();
            if (operatorId != null) {
                userRepository.findById(operatorId).ifPresent(auditLog::setOperator);
            }

            adminAuditLogRepository.save(auditLog);
        } catch (RuntimeException ex) {
            log.warn("记录后台操作日志失败: module={}, action={}, targetType={}, targetId={}, reason={}",
                    moduleName, action, targetType, targetId, ex.getMessage());
        }
    }

    private Long getCurrentOperatorIdOrNull() {
        RequestAttributes attrs = RequestContextHolder.getRequestAttributes();
        if (!(attrs instanceof ServletRequestAttributes servletAttributes)) {
            return null;
        }

        String userIdHeader = servletAttributes.getRequest().getHeader("X-User-Id");
        if (userIdHeader == null || userIdHeader.isBlank()) {
            return null;
        }

        try {
            return Long.parseLong(userIdHeader);
        } catch (NumberFormatException ex) {
            log.warn("X-User-Id 头格式错误: {}", userIdHeader);
            return null;
        }
    }

    private String resolveRequestIpAddress() {
        RequestAttributes attrs = RequestContextHolder.getRequestAttributes();
        if (!(attrs instanceof ServletRequestAttributes servletAttributes)) {
            return null;
        }

        String forwardedFor = servletAttributes.getRequest().getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) {
            return forwardedFor.split(",")[0].trim();
        }

        String realIp = servletAttributes.getRequest().getHeader("X-Real-IP");
        if (realIp != null && !realIp.isBlank()) {
            return realIp.trim();
        }

        return servletAttributes.getRequest().getRemoteAddr();
    }

    private Map<String, String> settingLabels() {
        Map<String, String> labels = new HashMap<>();
        labels.put("compactTable", "紧凑表格");
        labels.put("confirmActions", "危险操作二次确认");
        labels.put("pageSize", "默认分页大小");
        labels.put("contentAuditEnabled", "内容巡检开关");
        labels.put("allowPublicRegistration", "开放用户注册");
        labels.put("maxUploadSizeMb", "最大上传大小");
        labels.put("maintenanceNotice", "维护公告");
        return labels;
    }
}
