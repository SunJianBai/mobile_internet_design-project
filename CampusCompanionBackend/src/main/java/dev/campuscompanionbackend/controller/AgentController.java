package dev.campuscompanionbackend.controller;

import dev.campuscompanionbackend.dto.response.ApiResponse;
import dev.campuscompanionbackend.entity.AiConversation;
import dev.campuscompanionbackend.entity.AiMemory;
import dev.campuscompanionbackend.entity.AiMessage;
import dev.campuscompanionbackend.service.AgentService;
import dev.campuscompanionbackend.service.impl.AgentStreamService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/v1/agent")
@RequiredArgsConstructor
public class AgentController extends BaseController {

    private final AgentService agentService;
    private final AgentStreamService agentStreamService;

    // ==================== 会话管理 ====================

    @PostMapping("/conversations")
    public ApiResponse<Map<String, Object>> createConversation(
            @RequestHeader(value = "X-User-Id") Long userId) {
        log.info("创建新会话, userId={}", userId);
        AiConversation conv = agentService.createConversation(userId);
        return success(toConversationMap(conv));
    }

    @GetMapping("/conversations")
    public ApiResponse<List<Map<String, Object>>> listConversations(
            @RequestHeader(value = "X-User-Id") Long userId) {
        List<AiConversation> convs = agentService.listConversations(userId);
        List<Map<String, Object>> result = convs.stream().map(this::toConversationMap).toList();
        return success(result);
    }

    @GetMapping("/conversations/{cid}/messages")
    public ApiResponse<List<Map<String, Object>>> getMessages(
            @RequestHeader(value = "X-User-Id") Long userId,
            @PathVariable Long cid) {
        List<AiMessage> messages = agentService.getMessages(userId, cid);
        List<Map<String, Object>> result = messages.stream().map(this::toMessageMap).toList();
        return success(result);
    }

    @DeleteMapping("/conversations/{cid}")
    public ApiResponse<Void> deleteConversation(
            @RequestHeader(value = "X-User-Id") Long userId,
            @PathVariable Long cid) {
        agentService.deleteConversation(userId, cid);
        return success(null);
    }

    // ==================== 发送消息（核心） ====================

    @PostMapping("/conversations/{cid}/messages")
    public ApiResponse<Map<String, Object>> sendMessage(
            @RequestHeader(value = "X-User-Id") Long userId,
            @PathVariable Long cid,
            @RequestBody Map<String, String> body) {
        String message = body.get("message");
        if (message == null || message.isBlank()) {
            return error("消息内容不能为空");
        }
        log.info("Agent 收到消息, userId={}, cid={}, message={}", userId, cid,
                message.length() > 50 ? message.substring(0, 50) + "..." : message);

        try {
            AiMessage reply = agentService.sendMessage(userId, cid, message);
            return success(toMessageMap(reply));
        } catch (Exception e) {
            log.error("Agent 处理消息失败", e);
            return error("AI 服务暂时不可用: " + e.getMessage());
        }
    }

    // ==================== SSE 流式发送消息 ====================

    @PostMapping(value = "/conversations/{cid}/messages/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamMessage(
            @RequestHeader(value = "X-User-Id") Long userId,
            @PathVariable Long cid,
            @RequestBody Map<String, String> body) {
        String message = body.get("message");
        if (message == null || message.isBlank()) {
            SseEmitter emitter = new SseEmitter(0L);
            try {
                emitter.send(SseEmitter.event().name("error").data("消息内容不能为空"));
                emitter.complete();
            } catch (Exception ignored) {}
            return emitter;
        }
        log.info("Agent SSE 收到消息, userId={}, cid={}", userId, cid);
        return agentStreamService.streamMessage(userId, cid, message);
    }

    // ==================== 记忆管理 ====================

    @GetMapping("/memory")
    public ApiResponse<List<Map<String, Object>>> getMemories(
            @RequestHeader(value = "X-User-Id") Long userId) {
        List<AiMemory> memories = agentService.getMemories(userId);
        List<Map<String, Object>> result = memories.stream().map(this::toMemoryMap).toList();
        return success(result);
    }

    @DeleteMapping("/memory/{memId}")
    public ApiResponse<Void> deleteMemory(
            @RequestHeader(value = "X-User-Id") Long userId,
            @PathVariable Long memId) {
        agentService.deleteMemory(userId, memId);
        return success(null);
    }

    // ==================== DTO 转换 ====================

    private Map<String, Object> toConversationMap(AiConversation conv) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("cid", conv.getCid());
        map.put("title", conv.getTitle());
        map.put("createdAt", conv.getCreatedAt());
        map.put("updatedAt", conv.getUpdatedAt());
        return map;
    }

    private Map<String, Object> toMessageMap(AiMessage msg) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("mid", msg.getMid());
        map.put("role", msg.getRole());
        map.put("content", msg.getContent());
        map.put("toolName", msg.getToolName());
        map.put("tokenCount", msg.getTokenCount());
        map.put("createdAt", msg.getCreatedAt());
        return map;
    }

    private Map<String, Object> toMemoryMap(AiMemory mem) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put("memId", mem.getMemId());
        map.put("category", mem.getCategory());
        map.put("content", mem.getContent());
        map.put("source", mem.getSource());
        map.put("createdAt", mem.getCreatedAt());
        return map;
    }
}
