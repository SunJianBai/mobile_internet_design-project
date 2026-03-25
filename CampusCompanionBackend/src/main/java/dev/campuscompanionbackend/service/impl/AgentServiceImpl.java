package dev.campuscompanionbackend.service.impl;

import dev.campuscompanionbackend.entity.*;
import dev.campuscompanionbackend.exception.ParamValidationFailedException;
import dev.campuscompanionbackend.repository.*;
import dev.campuscompanionbackend.service.AgentService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;

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

    private static final int MAX_HISTORY_MESSAGES = 40;

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
        try {
            Map<String, Object> result = pythonAgentClient.chat(user, history, userMessage);
            assistantReply = (String) result.get("reply");
            if (assistantReply == null || assistantReply.isBlank()) {
                assistantReply = "抱歉，我暂时无法回复。";
            }
        } catch (Exception e) {
            log.error("Python Agent 调用失败", e);
            assistantReply = "AI 服务暂时不可用，请稍后再试。";
        }

        // 5. 保存 AI 回复
        AiMessage aiMsg = saveMessage(conv, "assistant", assistantReply, null, null);

        // 6. 异步提取记忆
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

    // ==================== 异步记忆提取（通过 Python Agent） ====================

    @Async
    public void extractMemoryAsync(User user, String userMessage, String assistantReply) {
        try {
            List<Map<String, String>> extracted = pythonAgentClient.extractMemory(userMessage, assistantReply);
            if (extracted == null || extracted.isEmpty()) return;

            List<AiMemory> existing = memoryRepository.findByUserOrderByUpdatedAtDesc(user);

            for (Map<String, String> m : extracted) {
                String category = m.get("category");
                String content = m.get("content");
                if (category == null || content == null) continue;

                // 去重：内容互包含则跳过
                boolean isDuplicate = existing.stream().anyMatch(e ->
                        e.getCategory().equals(category) &&
                                (e.getContent().contains(content) || content.contains(e.getContent()))
                );
                if (isDuplicate) continue;

                AiMemory memory = new AiMemory();
                memory.setUser(user);
                memory.setCategory(category);
                memory.setContent(content);
                memory.setSource("auto-extracted");
                memoryRepository.save(memory);
            }
        } catch (Exception e) {
            log.warn("记忆提取失败: {}", e.getMessage());
        }
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
        AiMessage msg = new AiMessage();
        msg.setConversation(conv);
        msg.setRole(role);
        msg.setContent(content);
        msg.setToolName(toolName);
        msg.setTokenCount(tokenCount);
        return messageRepository.save(msg);
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
