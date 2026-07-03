package dev.campushubbackend.service.impl;

import dev.campushubbackend.entity.*;
import dev.campushubbackend.exception.ParamValidationFailedException;
import dev.campushubbackend.repository.AiConversationRepository;
import dev.campushubbackend.repository.AiMessageRepository;
import dev.campushubbackend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import tools.jackson.databind.ObjectMapper;

import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * SSE 流式 Agent 服务 —— 代理 Python LangChain Agent 的 SSE 流。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentStreamService {

    private final AiConversationRepository conversationRepository;
    private final AiMessageRepository messageRepository;
    private final UserRepository userRepository;
    private final AgentServiceImpl agentService;
    private final PythonAgentClient pythonAgentClient;
    private final ObjectMapper objectMapper;

    private final ExecutorService executor = Executors.newCachedThreadPool();

    public SseEmitter streamMessage(Long userId, Long conversationId, String userMessage) {
        SseEmitter emitter = new SseEmitter(300_000L); // 5min timeout

        executor.execute(() -> {
            try {
                doStream(emitter, userId, conversationId, userMessage);
            } catch (Exception e) {
                log.error("SSE 流式处理失败", e);
                try {
                    emitter.send(SseEmitter.event().name("error").data("AI 服务异常: " + e.getMessage()));
                } catch (Exception ignored) {}
                emitter.completeWithError(e);
            }
        });

        return emitter;
    }

    private void doStream(SseEmitter emitter, Long userId, Long conversationId, String userMessage) throws Exception {
        sendAgentStep(emitter, "gateway", "已收到消息", "正在准备会话上下文并连接智能体服务", "running");

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ParamValidationFailedException("用户不存在"));
        AiConversation conv = conversationRepository.findByCidAndUser(conversationId, user)
                .orElseThrow(() -> new ParamValidationFailedException("会话不存在"));

        // 保存用户消息
        agentService.saveMessage(conv, "user", userMessage, null, null);

        // 更新标题
        List<AiMessage> allMessages = messageRepository.findByConversationOrderByCreatedAtAsc(conv);
        if (allMessages.size() == 1) {
            String title = userMessage.length() > 30 ? userMessage.substring(0, 30) + "..." : userMessage;
            conv.setTitle(title);
            conversationRepository.save(conv);
        }

        // 构建历史
        List<Map<String, String>> history = agentService.buildHistory(allMessages);
        sendAgentStep(emitter, "context", "上下文准备完成", "正在把历史消息和长期记忆发送给 AI 调度器", "completed");

        // 流式调用 Python Agent，逐 chunk 转发 SSE
        StringBuilder fullReply = new StringBuilder();
        List<Map<?, ?>> committedMemories = new ArrayList<>();
        List<Map<String, Object>> uiOperations = new ArrayList<>();
        List<Object> uiArtifacts = new ArrayList<>();

        pythonAgentClient.streamChat(user, history, userMessage,
                // onDelta
                delta -> {
                    try {
                        fullReply.append(delta);
                        emitter.send(SseEmitter.event().name("delta").data(delta));
                    } catch (Exception e) {
                        log.warn("发送 SSE delta 失败: {}", e.getMessage());
                    }
                },
                // onToolCall
                (eventName, data) -> {
                    try {
                        recordUiEvent(eventName, data, uiOperations, uiArtifacts);
                        if ("memory_commit".equals(eventName)) {
                            parseMemoryCommit(data).ifPresent(committedMemories::add);
                        }
                        emitter.send(SseEmitter.event().name(eventName).data(data));
                    } catch (Exception e) {
                        log.warn("发送 SSE status 失败: {}", e.getMessage());
                    }
                },
                // onDone
                () -> {
                    try {
                        // 保存完整回复
                        String replyText = fullReply.toString();
                        if (replyText.isBlank()) replyText = "抱歉，我暂时无法回复。";
                        String uiMetadata = agentService.buildUiMetadataJson(
                                finalizeUiOperations(uiOperations),
                                uiArtifacts
                        );
                        agentService.saveMessage(conv, "assistant", replyText, null, null, uiMetadata);

                        // 先应用用户明确确认的记忆操作，再异步提取普通对话中的隐式记忆
                        agentService.applyCommittedMemoryOperations(user, committedMemories);
                        agentService.extractMemoryAsync(user, userMessage, replyText);

                        // 更新会话时间
                        conv.setUpdatedAt(LocalDateTime.now());
                        conversationRepository.save(conv);

                        emitter.send(SseEmitter.event().name("done").data(""));
                        emitter.complete();
                    } catch (Exception e) {
                        log.error("SSE 完成处理失败", e);
                    }
                },
                // onError
                error -> {
                    try {
                        emitter.send(SseEmitter.event().name("error").data(error));
                        emitter.complete();
                    } catch (Exception e) {
                        log.warn("发送 SSE error 失败: {}", e.getMessage());
                    }
                }
        );
    }

    private void recordUiEvent(
            String eventName,
            String data,
            List<Map<String, Object>> operations,
            List<Object> artifacts
    ) {
        Map<String, Object> payload = parseEventPayload(data);
        Map<String, Object> operation = agentService.normalizeUiOperation(eventName, payload, false);
        mergeOperation(operations, operation);

        if ("artifact".equals(eventName) || "confirm_required".equals(eventName)) {
            Map<String, Object> artifact = new LinkedHashMap<>(payload);
            if (!artifact.containsKey("type") && "confirm_required".equals(eventName)) {
                artifact.put("type", "confirmation");
            }
            mergeArtifact(artifacts, artifact);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseEventPayload(String data) {
        if (data == null || data.isBlank()) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, Object> parsed = objectMapper.readValue(data, Map.class);
            return parsed == null ? new LinkedHashMap<>() : parsed;
        } catch (Exception e) {
            Map<String, Object> fallback = new LinkedHashMap<>();
            fallback.put("title", data);
            return fallback;
        }
    }

    private void mergeOperation(List<Map<String, Object>> operations, Map<String, Object> operation) {
        String phase = String.valueOf(operation.getOrDefault("phase", ""));
        String eventName = String.valueOf(operation.getOrDefault("eventName", ""));
        String state = String.valueOf(operation.getOrDefault("state", ""));
        if (!"running".equals(state)) {
            for (int i = operations.size() - 1; i >= 0; i--) {
                Map<String, Object> previous = operations.get(i);
                if (phase.equals(String.valueOf(previous.getOrDefault("phase", "")))
                        && eventName.equals(String.valueOf(previous.getOrDefault("eventName", "")))) {
                    previous.putAll(operation);
                    return;
                }
            }
        }
        operations.add(operation);
    }

    private List<Map<String, Object>> finalizeUiOperations(List<Map<String, Object>> operations) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> operation : operations) {
            Map<String, Object> next = new LinkedHashMap<>(operation);
            if ("running".equals(String.valueOf(next.getOrDefault("state", "")))) {
                next.put("state", "completed");
            }
            result.add(next);
        }
        return result;
    }

    private void mergeArtifact(List<Object> artifacts, Map<String, Object> artifact) {
        String key = artifactKey(artifact);
        for (Object item : artifacts) {
            if (item instanceof Map<?, ?> existing && key.equals(artifactKey(existing))) {
                return;
            }
        }
        artifacts.add(artifact);
    }

    private String artifactKey(Map<?, ?> artifact) {
        Object id = artifact.get("id");
        if (id != null && !String.valueOf(id).isBlank()) {
            return String.valueOf(id);
        }
        return String.valueOf(artifact.get("type") == null ? "" : artifact.get("type"))
                + ":" + String.valueOf(artifact.get("title") == null ? "" : artifact.get("title"))
                + ":" + String.valueOf(artifact.get("actionKind") == null ? "" : artifact.get("actionKind"));
    }

    @SuppressWarnings("unchecked")
    private Optional<Map<?, ?>> parseMemoryCommit(String data) {
        try {
            Map<String, Object> parsed = objectMapper.readValue(data, Map.class);
            return Optional.of(parsed);
        } catch (Exception e) {
            log.warn("解析记忆提交事件失败: {}", e.getMessage());
            return Optional.empty();
        }
    }

    private void sendAgentStep(SseEmitter emitter, String phase, String title, String detail, String state) {
        try {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("phase", phase);
            payload.put("title", title);
            payload.put("detail", detail);
            payload.put("state", state);
            emitter.send(SseEmitter.event().name("agent_step").data(toJson(payload)));
        } catch (Exception e) {
            log.warn("发送 SSE 状态失败: {}", e.getMessage());
        }
    }

    private String toJson(Map<String, Object> payload) {
        StringBuilder json = new StringBuilder("{");
        Iterator<Map.Entry<String, Object>> iterator = payload.entrySet().iterator();
        while (iterator.hasNext()) {
            Map.Entry<String, Object> entry = iterator.next();
            json.append('"').append(escapeJson(entry.getKey())).append("\":");
            Object value = entry.getValue();
            if (value == null) {
                json.append("null");
            } else {
                json.append('"').append(escapeJson(String.valueOf(value))).append('"');
            }
            if (iterator.hasNext()) {
                json.append(',');
            }
        }
        json.append('}');
        return json.toString();
    }

    private String escapeJson(String value) {
        return value
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
