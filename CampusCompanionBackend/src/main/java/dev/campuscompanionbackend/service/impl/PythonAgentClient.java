package dev.campuscompanionbackend.service.impl;

import dev.campuscompanionbackend.entity.AiMemory;
import dev.campuscompanionbackend.entity.User;
import dev.campuscompanionbackend.repository.AiMemoryRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.function.Consumer;

/**
 * Java → Python Agent 服务的 HTTP 客户端。
 * 负责将对话上下文发送给 Python LangChain Agent，接收回复。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PythonAgentClient {

    private final AiMemoryRepository memoryRepository;
    private final ObjectMapper objectMapper;

    @Value("${agent.python.base-url:http://localhost:5000}")
    private String pythonBaseUrl;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(java.time.Duration.ofSeconds(10))
            .build();

    /**
     * 非流式调用 Python Agent
     *
     * @return {"reply": "...", "tool_calls": [...]}
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> chat(User user, List<Map<String, String>> history, String message) throws Exception {
        Map<String, Object> body = buildRequestBody(user, history, message);
        String json = objectMapper.writeValueAsString(body);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(pythonBaseUrl + "/chat"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                .timeout(java.time.Duration.ofSeconds(120))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new RuntimeException("Python Agent 返回错误: " + response.statusCode() + " - " + response.body());
        }

        Map<String, Object> result = objectMapper.readValue(response.body(), Map.class);
        return (Map<String, Object>) result.get("data");
    }

    /**
     * 流式调用 Python Agent（SSE），逐行回调
     */
    public void streamChat(User user, List<Map<String, String>> history, String message,
                           Consumer<String> onDelta,
                           Consumer<String> onToolCall,
                           Runnable onDone,
                           Consumer<String> onError) throws Exception {
        Map<String, Object> body = buildRequestBody(user, history, message);
        String json = objectMapper.writeValueAsString(body);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(pythonBaseUrl + "/stream"))
                .header("Content-Type", "application/json")
                .header("Accept", "text/event-stream")
                .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                .timeout(java.time.Duration.ofSeconds(300))
                .build();

        HttpResponse<java.io.InputStream> response = httpClient.send(request,
                HttpResponse.BodyHandlers.ofInputStream());

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
            String line;
            String currentEvent = "message";
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("event:")) {
                    currentEvent = line.substring(6).trim();
                } else if (line.startsWith("data:")) {
                    String data = line.substring(5).trim();
                    switch (currentEvent) {
                        case "delta" -> onDelta.accept(data);
                        case "tool_call" -> onToolCall.accept(data);
                        case "done" -> onDone.run();
                        case "error" -> onError.accept(data);
                    }
                }
            }
        }
    }

    /**
     * 调用 Python 提取记忆
     */
    @SuppressWarnings("unchecked")
    public List<Map<String, String>> extractMemory(String userMessage, String assistantReply) {
        try {
            Map<String, String> body = Map.of(
                    "user_message", userMessage,
                    "assistant_reply", assistantReply
            );
            String json = objectMapper.writeValueAsString(body);

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(pythonBaseUrl + "/extract-memory"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                    .timeout(java.time.Duration.ofSeconds(30))
                    .build();

            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 200) {
                Map<String, Object> result = objectMapper.readValue(response.body(), Map.class);
                return (List<Map<String, String>>) result.get("data");
            }
        } catch (Exception e) {
            log.warn("Python 记忆提取失败: {}", e.getMessage());
        }
        return List.of();
    }

    // ==================== 内部方法 ====================

    private Map<String, Object> buildRequestBody(User user, List<Map<String, String>> history, String message) {
        // 用户信息
        Map<String, Object> userInfo = new LinkedHashMap<>();
        userInfo.put("uid", user.getUid());
        userInfo.put("nickname", user.getNickname());

        // 用户记忆
        List<AiMemory> memoryEntities = memoryRepository.findByUserOrderByUpdatedAtDesc(user);
        List<Map<String, String>> memories = memoryEntities.stream()
                .map(m -> Map.of("category", m.getCategory(), "content", m.getContent()))
                .toList();

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("user_info", userInfo);
        body.put("memories", memories);
        body.put("history", history);
        body.put("message", message);
        return body;
    }
}
