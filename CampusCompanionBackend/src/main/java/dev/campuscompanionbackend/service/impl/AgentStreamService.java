package dev.campuscompanionbackend.service.impl;

import dev.campuscompanionbackend.entity.*;
import dev.campuscompanionbackend.exception.ParamValidationFailedException;
import dev.campuscompanionbackend.repository.AiConversationRepository;
import dev.campuscompanionbackend.repository.AiMessageRepository;
import dev.campuscompanionbackend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

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

        // 流式调用 Python Agent，逐 chunk 转发 SSE
        StringBuilder fullReply = new StringBuilder();

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
                status -> {
                    try {
                        emitter.send(SseEmitter.event().name("status").data(status));
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
                        agentService.saveMessage(conv, "assistant", replyText, null, null);

                        // 异步提取记忆
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
}
