package dev.campushubbackend.service.impl;

import dev.campushubbackend.entity.*;
import dev.campushubbackend.exception.ParamValidationFailedException;
import dev.campushubbackend.repository.*;
import dev.campushubbackend.service.AgentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.ObjectMapper;

import java.time.LocalDateTime;
import java.util.*;
import java.util.regex.Pattern;

/**
 * Agent 服务实现 —— 会话/消息/记忆的持久化 + 代理到 Python LangChain Agent。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentServiceImpl implements AgentService {

    private final AiConversationRepository conversationRepository;
    private final AiMessageRepository messageRepository;
    private final AiMemoryRepository memoryRepository;
    private final UserRepository userRepository;
    private final PythonAgentClient pythonAgentClient;
    private final ObjectMapper objectMapper;

    private static final int MAX_HISTORY_MESSAGES = 40;
    static final int MAX_AUTO_MEMORIES_PER_TURN = 2;
    private static final int MIN_MEMORY_CONTENT_LENGTH = 6;
    private static final int MIN_COMMITTED_MEMORY_CONTENT_LENGTH = 4;
    private static final int MAX_MEMORY_CONTENT_LENGTH = 120;
    private static final Pattern COORDINATE_PATTERN = Pattern.compile("\\d{2,3}\\.\\d{3,}\\s*[,，]\\s*\\d{1,3}\\.\\d{3,}");
    private static final List<String> STRICT_TRANSIENT_MEMORY_MARKERS = List.of(
            "坐标", "经纬度", "地图", "导航", "路线", "草稿", "尚未提供", "工具返回", "查询结果", "搜索结果"
    );
    private static final List<String> SOFT_TRANSIENT_MEMORY_MARKERS = List.of(
            "当前", "目前", "这次", "本次", "此次", "刚才", "刚刚", "今天", "今晚", "明天", "后天",
            "正在", "查询", "搜索", "寻找", "想找", "想要找", "附近", "周边", "这家", "店铺", "会所"
    );
    private static final List<String> DURABLE_MEMORY_MARKERS = List.of(
            "喜欢", "偏好", "倾向", "习惯", "经常", "常去", "不喜欢", "讨厌", "过敏", "默认", "以后", "长期", "就读", "住在"
    );
    private static final List<String> STABLE_FACT_MARKERS = List.of(
            "专业", "年级", "学院", "学校", "校区", "来自", "手机号", "邮箱"
    );
    private static final List<String> ONE_OFF_INTENT_PREFIXES = List.of(
            "用户想", "用户正在", "用户需要", "用户询问", "用户查找", "用户搜索", "用户提供", "用户计划", "用户准备"
    );
    private static final List<String> NO_SIGNAL_MEMORY_MARKERS = List.of(
            "none", "没有提取到", "没有值得提取", "没有可提取", "无事实", "无明确事实", "无可记忆",
            "不明确", "无法判断", "无法确定", "测试系统反应", "习惯性输入错误"
    );
    private static final List<String> LOW_CONFIDENCE_MEMORY_MARKERS = List.of(
            "可能", "疑似", "似乎", "大概", "也许", "猜测", "推测", "不确定"
    );

    // ==================== 会话管理 ====================

    @Override
    @Transactional
    public AiConversation createConversation(Long userId) {
        User user = findUserOrThrow(userId);
        AiConversation conv = new AiConversation();
        conv.setUser(user);
        conv.setTitle("新对话");
        return conversationRepository.save(conv);
    }

    @Override
    public List<AiConversation> listConversations(Long userId) {
        User user = findUserOrThrow(userId);
        return conversationRepository.findByUserOrderByUpdatedAtDesc(user);
    }

    @Override
    public List<AiMessage> getMessages(Long userId, Long conversationId) {
        AiConversation conv = findConversationOrThrow(userId, conversationId);
        return messageRepository.findByConversationOrderByCreatedAtAsc(conv);
    }

    @Override
    @Transactional
    public void deleteConversation(Long userId, Long conversationId) {
        AiConversation conv = findConversationOrThrow(userId, conversationId);
        messageRepository.deleteByConversation(conv);
        conversationRepository.delete(conv);
    }

    // ==================== 核心：代理到 Python Agent ====================

    @Override
    @Transactional
    public AiMessage sendMessage(Long userId, Long conversationId, String userMessage) {
        AiConversation conv = findConversationOrThrow(userId, conversationId);
        User user = conv.getUser();

        // 1. 保存用户消息
        saveMessage(conv, "user", userMessage, null, null);

        // 2. 自动更新会话标题（首条消息时）
        List<AiMessage> allMessages = messageRepository.findByConversationOrderByCreatedAtAsc(conv);
        if (allMessages.size() == 1) {
            String title = userMessage.length() > 30 ? userMessage.substring(0, 30) + "..." : userMessage;
            conv.setTitle(title);
            conversationRepository.save(conv);
        }

        // 3. 构建历史消息（仅 user/assistant，跳过 tool）
        List<Map<String, String>> history = buildHistory(allMessages);

        // 4. 调用 Python LangChain Agent
        String assistantReply;
        String uiMetadata = null;
        List<Map<?, ?>> committedMemories = List.of();
        try {
            Map<String, Object> result = pythonAgentClient.chat(user, history, userMessage);
            assistantReply = (String) result.get("reply");
            if (assistantReply == null || assistantReply.isBlank()) {
                assistantReply = "抱歉，我暂时无法回复。";
            }
            uiMetadata = buildUiMetadataJson(buildNonStreamingOperations(result), coerceUiList(result.get("artifacts")));
            committedMemories = coerceMemoryCommits(result.get("memory_commits"));
        } catch (Exception e) {
            log.error("Python Agent 调用失败", e);
            assistantReply = "AI 服务暂时不可用，请稍后再试。";
        }

        // 5. 保存 AI 回复
        AiMessage aiMsg = saveMessage(conv, "assistant", assistantReply, null, null, uiMetadata);

        // 6. 先保存用户明确确认的记忆，再异步提取普通对话中的隐式记忆
        applyCommittedMemoryOperations(user, committedMemories);
        extractMemoryAsync(user, userMessage, assistantReply);

        // 7. 更新会话时间
        conv.setUpdatedAt(LocalDateTime.now());
        conversationRepository.save(conv);

        return aiMsg;
    }

    // ==================== 记忆管理 ====================

    @Override
    public List<AiMemory> getMemories(Long userId) {
        User user = findUserOrThrow(userId);
        return memoryRepository.findByUserOrderByUpdatedAtDesc(user);
    }

    @Override
    @Transactional
    public void deleteMemory(Long userId, Long memoryId) {
        AiMemory memory = memoryRepository.findById(memoryId)
                .orElseThrow(() -> new ParamValidationFailedException("记忆不存在"));
        if (!memory.getUser().getUid().equals(userId)) {
            throw new ParamValidationFailedException("无权删除该记忆");
        }
        memoryRepository.delete(memory);
    }

    @Transactional
    public void applyCommittedMemoryOperations(User user, List<? extends Map<?, ?>> operations) {
        if (user == null || operations == null || operations.isEmpty()) {
            return;
        }

        List<AiMemory> existing = memoryRepository.findByUserOrderByUpdatedAtDesc(user);
        for (Map<String, String> item : filterCommittedMemoryOperations(operations, existing)) {
            String operation = item.get("operation");
            String content = item.get("content");
            if ("delete".equals(operation)) {
                deleteMatchingCommittedMemory(user, content);
                existing = memoryRepository.findByUserOrderByUpdatedAtDesc(user);
                continue;
            }

            AiMemory memory = new AiMemory();
            memory.setUser(user);
            memory.setCategory(item.get("category"));
            memory.setContent(content);
            memory.setSource("confirmed-chat");
            memoryRepository.save(memory);
            existing.add(memory);
        }
    }

    static List<Map<String, String>> filterCommittedMemoryOperations(
            List<? extends Map<?, ?>> operations,
            List<AiMemory> existing
    ) {
        if (operations == null || operations.isEmpty()) {
            return List.of();
        }

        Set<String> seen = new HashSet<>();
        for (AiMemory memory : Optional.ofNullable(existing).orElse(List.of())) {
            String normalized = normalizeMemoryText(memory.getContent());
            if (!normalized.isBlank()) {
                seen.add(normalized);
            }
        }

        List<Map<String, String>> filtered = new ArrayList<>();
        for (Map<?, ?> operation : operations) {
            if (operation == null) {
                continue;
            }

            String action = normalizeCommittedMemoryOperation(stringValue(operation.get("operation")));
            String category = normalizeMemoryCategory(stringValue(operation.get("category")));
            String content = sanitizeMemoryContent(stringValue(operation.get("content")));
            if (category.isBlank()
                    || content.length() < MIN_COMMITTED_MEMORY_CONTENT_LENGTH
                    || content.length() > MAX_MEMORY_CONTENT_LENGTH) {
                continue;
            }
            if (COORDINATE_PATTERN.matcher(content).find()) {
                continue;
            }

            String normalized = normalizeMemoryText(content);
            if (normalized.isBlank()) {
                continue;
            }

            if ("save".equals(action)) {
                String compact = compactForPolicy(content);
                if (isNoSignalMemoryContent(compact)
                        || containsAny(compact, STRICT_TRANSIENT_MEMORY_MARKERS)
                        || startsWithAny(compact, ONE_OFF_INTENT_PREFIXES)
                        || isDuplicateMemory(normalized, seen)) {
                    continue;
                }
                seen.add(normalized);
            }

            filtered.add(Map.of(
                    "operation", action,
                    "category", category,
                    "content", content
            ));
        }
        return filtered;
    }

    private void deleteMatchingCommittedMemory(User user, String content) {
        String target = normalizeMemoryText(content);
        if (target.isBlank()) {
            return;
        }
        List<AiMemory> existing = memoryRepository.findByUserOrderByUpdatedAtDesc(user);
        for (AiMemory memory : existing) {
            String normalized = normalizeMemoryText(memory.getContent());
            if (!normalized.isBlank()
                    && (normalized.contains(target)
                    || target.contains(normalized)
                    || charBigramSimilarity(normalized, target) >= 0.72)) {
                memoryRepository.delete(memory);
            }
        }
    }

    private static List<Map<?, ?>> coerceMemoryCommits(Object value) {
        if (!(value instanceof List<?> list)) {
            return List.of();
        }
        List<Map<?, ?>> result = new ArrayList<>();
        for (Object item : list) {
            if (item instanceof Map<?, ?> map) {
                result.add(map);
            }
        }
        return result;
    }

    private static String normalizeCommittedMemoryOperation(String value) {
        String normalized = Optional.ofNullable(value).orElse("").trim().toLowerCase(Locale.ROOT);
        if (normalized.contains("delete") || normalized.contains("remove") || normalized.contains("forget")
                || normalized.contains("删除") || normalized.contains("忘记") || normalized.contains("移除")) {
            return "delete";
        }
        return "save";
    }

    private static String stringValue(Object value) {
        if (value == null) {
            return "";
        }
        String text = String.valueOf(value).trim();
        return "null".equalsIgnoreCase(text) ? "" : text;
    }

    // ==================== 异步记忆提取（通过 Python Agent） ====================

    @Async
    public void extractMemoryAsync(User user, String userMessage, String assistantReply) {
        try {
            List<Map<String, String>> extracted = pythonAgentClient.extractMemory(userMessage, assistantReply);
            if (extracted == null || extracted.isEmpty()) return;

            List<AiMemory> existing = memoryRepository.findByUserOrderByUpdatedAtDesc(user);

            List<Map<String, String>> filtered = filterAutoExtractedMemories(
                    extracted,
                    existing,
                    userMessage,
                    assistantReply
            );

            for (Map<String, String> m : filtered) {
                AiMemory memory = new AiMemory();
                memory.setUser(user);
                memory.setCategory(m.get("category"));
                memory.setContent(m.get("content"));
                memory.setSource("auto-extracted");
                memoryRepository.save(memory);
            }
        } catch (Exception e) {
            log.warn("记忆提取失败: {}", e.getMessage());
        }
    }

    static List<Map<String, String>> filterAutoExtractedMemories(
            List<Map<String, String>> extracted,
            List<AiMemory> existing,
            String userMessage,
            String assistantReply
    ) {
        if (extracted == null || extracted.isEmpty()) {
            return List.of();
        }

        Set<String> seen = new HashSet<>();
        for (AiMemory memory : Optional.ofNullable(existing).orElse(List.of())) {
            String normalized = normalizeMemoryText(memory.getContent());
            if (!normalized.isBlank()) {
                seen.add(normalized);
            }
        }

        List<Map<String, String>> filtered = new ArrayList<>();
        for (Map<String, String> item : extracted) {
            if (filtered.size() >= MAX_AUTO_MEMORIES_PER_TURN) {
                break;
            }
            if (item == null) {
                continue;
            }

            String category = normalizeMemoryCategory(item.get("category"));
            String content = sanitizeMemoryContent(item.get("content"));
            if (!shouldKeepAutoMemory(category, content, userMessage, assistantReply)) {
                continue;
            }

            String normalized = normalizeMemoryText(content);
            if (isDuplicateMemory(normalized, seen)) {
                continue;
            }

            seen.add(normalized);
            filtered.add(Map.of("category", category, "content", content));
        }
        return filtered;
    }

    static boolean shouldKeepAutoMemory(
            String category,
            String content,
            String userMessage,
            String assistantReply
    ) {
        if (category == null || category.isBlank() || content == null || content.isBlank()) {
            return false;
        }
        if (content.length() < MIN_MEMORY_CONTENT_LENGTH || content.length() > MAX_MEMORY_CONTENT_LENGTH) {
            return false;
        }
        if (COORDINATE_PATTERN.matcher(content).find()) {
            return false;
        }

        String compact = compactForPolicy(content);
        if (compact.isBlank()) {
            return false;
        }
        if (isNoSignalMemoryContent(compact) || containsAny(compact, LOW_CONFIDENCE_MEMORY_MARKERS)) {
            return false;
        }
        if (containsAny(compact, STRICT_TRANSIENT_MEMORY_MARKERS)) {
            return false;
        }
        if (startsWithAny(compact, ONE_OFF_INTENT_PREFIXES)) {
            return false;
        }
        if (containsAny(compact, SOFT_TRANSIENT_MEMORY_MARKERS) && !containsAny(compact, DURABLE_MEMORY_MARKERS)) {
            return false;
        }

        String userCompact = compactForPolicy(userMessage);
        String assistantCompact = compactForPolicy(assistantReply);
        boolean looksLikeToolResult = !assistantCompact.isBlank()
                && assistantCompact.contains(compact)
                && !userCompact.contains(compact);
        if (looksLikeToolResult && !containsAny(compact, DURABLE_MEMORY_MARKERS)) {
            return false;
        }

        return containsAny(compact, DURABLE_MEMORY_MARKERS)
                || ("fact".equals(category) && containsAny(compact, STABLE_FACT_MARKERS));
    }

    static String normalizeMemoryCategory(String category) {
        String value = Optional.ofNullable(category).orElse("").trim().toLowerCase(Locale.ROOT);
        if (value.contains("preference") || value.contains("偏好")) {
            return "preference";
        }
        if (value.contains("behavior") || value.contains("habit") || value.contains("行为") || value.contains("习惯")) {
            return "behavior";
        }
        if (value.contains("fact") || value.contains("事实")) {
            return "fact";
        }
        return "";
    }

    static String sanitizeMemoryContent(String content) {
        return Optional.ofNullable(content)
                .orElse("")
                .replaceAll("\\s+", " ")
                .trim();
    }

    static String normalizeMemoryText(String content) {
        String value = compactForPolicy(content);
        return value
                .replace("用户", "")
                .replace("偏好", "喜欢")
                .replace("倾向于", "喜欢")
                .replace("倾向", "喜欢")
                .replace("进行", "")
                .replace("选择", "")
                .replace("一个", "")
                .replace("一种", "")
                .replace("的", "");
    }

    private static boolean isDuplicateMemory(String normalized, Set<String> seen) {
        if (normalized.isBlank()) {
            return true;
        }
        for (String existing : seen) {
            if (existing.length() >= MIN_MEMORY_CONTENT_LENGTH
                    && (existing.contains(normalized) || normalized.contains(existing))) {
                return true;
            }
            if (charBigramSimilarity(existing, normalized) >= 0.72) {
                return true;
            }
        }
        return false;
    }

    private static double charBigramSimilarity(String left, String right) {
        Set<String> leftBigrams = charBigrams(left);
        Set<String> rightBigrams = charBigrams(right);
        if (leftBigrams.isEmpty() || rightBigrams.isEmpty()) {
            return 0;
        }
        Set<String> intersection = new HashSet<>(leftBigrams);
        intersection.retainAll(rightBigrams);
        Set<String> union = new HashSet<>(leftBigrams);
        union.addAll(rightBigrams);
        return (double) intersection.size() / union.size();
    }

    private static Set<String> charBigrams(String value) {
        if (value == null || value.length() < 2) {
            return Set.of();
        }
        Set<String> bigrams = new HashSet<>();
        for (int i = 0; i < value.length() - 1; i++) {
            bigrams.add(value.substring(i, i + 2));
        }
        return bigrams;
    }

    private static String compactForPolicy(String value) {
        return Optional.ofNullable(value)
                .orElse("")
                .toLowerCase(Locale.ROOT)
                .replaceAll("[\\s\\p{Punct}，。！？；：、“”‘’（）()【】《》「」『』·]+", "");
    }

    private static boolean containsAny(String value, List<String> markers) {
        return markers.stream().anyMatch(value::contains);
    }

    private static boolean startsWithAny(String value, List<String> prefixes) {
        return prefixes.stream().anyMatch(value::startsWith);
    }

    private static boolean isNoSignalMemoryContent(String compact) {
        return "none".equals(compact) || containsAny(compact, NO_SIGNAL_MEMORY_MARKERS);
    }

    // ==================== 辅助方法 ====================

    /**
     * 将历史 AiMessage 转为 Python Agent 需要的格式
     */
    List<Map<String, String>> buildHistory(List<AiMessage> allMessages) {
        List<AiMessage> recent = allMessages;
        if (allMessages.size() > MAX_HISTORY_MESSAGES) {
            recent = allMessages.subList(allMessages.size() - MAX_HISTORY_MESSAGES, allMessages.size());
        }

        List<Map<String, String>> history = new ArrayList<>();
        for (AiMessage msg : recent) {
            if ("tool".equals(msg.getRole())) continue;
            history.add(Map.of("role", msg.getRole(), "content", msg.getContent()));
        }
        return history;
    }

    AiMessage saveMessage(AiConversation conv, String role, String content, String toolName, Integer tokenCount) {
        return saveMessage(conv, role, content, toolName, tokenCount, null);
    }

    AiMessage saveMessage(AiConversation conv, String role, String content, String toolName, Integer tokenCount, String uiMetadata) {
        AiMessage msg = new AiMessage();
        msg.setConversation(conv);
        msg.setRole(role);
        msg.setContent(content);
        msg.setToolName(toolName);
        msg.setTokenCount(tokenCount);
        msg.setUiMetadata(uiMetadata);
        return messageRepository.save(msg);
    }

    @SuppressWarnings("unchecked")
    List<Object> coerceUiList(Object value) {
        if (value instanceof List<?> list) {
            return new ArrayList<>((List<Object>) list);
        }
        return new ArrayList<>();
    }

    @SuppressWarnings("unchecked")
    List<Map<String, Object>> buildNonStreamingOperations(Map<String, Object> result) {
        List<Map<String, Object>> operations = new ArrayList<>();
        Object intentValue = result == null ? null : result.get("intent");
        if (intentValue instanceof Map<?, ?> intentMap) {
            Map<String, Object> intent = new LinkedHashMap<>();
            intentMap.forEach((key, value) -> intent.put(String.valueOf(key), value));
            operations.add(normalizeUiOperation("intent", intent, true));
        }
        Object toolCallsValue = result == null ? null : result.get("tool_calls");
        if (toolCallsValue instanceof List<?> toolCalls && !toolCalls.isEmpty()) {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("phase", "tool_call");
            payload.put("title", "工具调用完成");
            payload.put("detail", "已调用 " + toolCalls.size() + " 个工具");
            payload.put("state", "completed");
            operations.add(normalizeUiOperation("tool_call", payload, true));
        }
        return operations;
    }

    Map<String, Object> normalizeUiOperation(String eventName, Map<String, Object> payload, boolean finalizeRunning) {
        Map<String, Object> operation = new LinkedHashMap<>();
        String title = stringValue(payload.get("title"));
        if (title.isBlank()) {
            title = switch (eventName) {
                case "intent" -> "识别意图";
                case "artifact" -> "生成结果卡片";
                case "confirm_required" -> "等待确认";
                case "memory_commit" -> "提交长期记忆";
                default -> eventName;
            };
        }
        String detail = stringValue(payload.get("detail"));
        if (detail.isBlank()) {
            detail = stringValue(payload.get("summary"));
        }
        if ("intent".equals(eventName) && detail.isBlank()) {
            List<String> parts = new ArrayList<>();
            addIfPresent(parts, payload.get("primary_intent"));
            addIfPresent(parts, payload.get("operation_type"));
            if (Boolean.TRUE.equals(payload.get("requires_confirmation"))) {
                parts.add("需要确认");
            }
            detail = String.join(" · ", parts);
        }

        String state = stringValue(payload.get("state"));
        if (state.isBlank()) {
            state = "confirm_required".equals(eventName) ? "pending" : "running";
        }
        if (finalizeRunning && "running".equals(state)) {
            state = "completed";
        }

        operation.put("eventName", eventName);
        operation.put("phase", firstNonBlank(
                stringValue(payload.get("phase")),
                stringValue(payload.get("domain")),
                eventName
        ));
        operation.put("title", title);
        operation.put("detail", detail);
        operation.put("state", state);

        Map<String, Object> meta = new LinkedHashMap<>();
        putIfPresent(meta, "primaryIntent", payload.get("primary_intent"));
        putIfPresent(meta, "domain", payload.get("domain"));
        putIfPresent(meta, "operationType", payload.get("operation_type"));
        putIfPresent(meta, "confidence", payload.get("confidence"));
        putIfPresent(meta, "requiresConfirmation", payload.get("requires_confirmation"));
        operation.put("meta", meta);
        return operation;
    }

    String buildUiMetadataJson(List<Map<String, Object>> operations, List<Object> artifacts) {
        boolean hasOperations = operations != null && !operations.isEmpty();
        boolean hasArtifacts = artifacts != null && !artifacts.isEmpty();
        if (!hasOperations && !hasArtifacts) {
            return null;
        }
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("operations", hasOperations ? operations : List.of());
        metadata.put("artifacts", hasArtifacts ? artifacts : List.of());
        try {
            return objectMapper.writeValueAsString(metadata);
        } catch (Exception e) {
            log.warn("序列化 AI UI 元数据失败: {}", e.getMessage());
            return null;
        }
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return "";
    }

    private void addIfPresent(List<String> target, Object value) {
        String text = stringValue(value);
        if (!text.isBlank()) {
            target.add(text);
        }
    }

    private void putIfPresent(Map<String, Object> target, String key, Object value) {
        if (value != null) {
            target.put(key, value);
        }
    }

    User findUserOrThrow(Long userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new ParamValidationFailedException("用户不存在"));
    }

    AiConversation findConversationOrThrow(Long userId, Long conversationId) {
        User user = findUserOrThrow(userId);
        return conversationRepository.findByCidAndUser(conversationId, user)
                .orElseThrow(() -> new ParamValidationFailedException("会话不存在"));
    }
}
