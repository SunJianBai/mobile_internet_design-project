package dev.campuscompanionbackend.service;

import dev.campuscompanionbackend.entity.AiConversation;
import dev.campuscompanionbackend.entity.AiMemory;
import dev.campuscompanionbackend.entity.AiMessage;

import java.util.List;

public interface AgentService {

    /** 创建新会话 */
    AiConversation createConversation(Long userId);

    /** 获取用户的会话列表 */
    List<AiConversation> listConversations(Long userId);

    /** 获取某会话的消息历史 */
    List<AiMessage> getMessages(Long userId, Long conversationId);

    /** 删除会话 */
    void deleteConversation(Long userId, Long conversationId);

    /** 发送消息并获取 AI 回复（核心 Agent 循环） */
    AiMessage sendMessage(Long userId, Long conversationId, String userMessage);

    /** 获取用户的 AI 记忆列表 */
    List<AiMemory> getMemories(Long userId);

    /** 删除某条记忆 */
    void deleteMemory(Long userId, Long memoryId);
}
