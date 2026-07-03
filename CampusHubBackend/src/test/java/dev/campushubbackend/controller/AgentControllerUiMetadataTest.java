package dev.campushubbackend.controller;

import dev.campushubbackend.dto.response.ApiResponse;
import dev.campushubbackend.entity.AiConversation;
import dev.campushubbackend.entity.AiMemory;
import dev.campushubbackend.entity.AiMessage;
import dev.campushubbackend.service.AgentService;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class AgentControllerUiMetadataTest {

    @Test
    @SuppressWarnings("unchecked")
    void getMessagesRestoresOperationsAndArtifactsForHistory() {
        AiMessage message = new AiMessage();
        message.setMid(100L);
        message.setRole("assistant");
        message.setContent("我已经帮你查到了附近店铺。");
        message.setUiMetadata("""
                {
                  "operations": [
                    {
                      "eventName": "agent_step",
                      "phase": "map",
                      "title": "地图查询完成",
                      "state": "completed"
                    }
                  ],
                  "artifacts": [
                    {
                      "type": "guide",
                      "title": "附近推荐",
                      "items": [
                        {
                          "title": "沐春足道",
                          "meta": "116.180100,39.731200"
                        }
                      ]
                    }
                  ]
                }
                """);

        AgentController controller = new AgentController(
                new FakeAgentService(List.of(message)),
                null,
                new ObjectMapper()
        );

        ApiResponse<List<Map<String, Object>>> response = controller.getMessages(4L, 29L);

        assertEquals(200, response.getCode());
        Map<String, Object> mapped = response.getData().get(0);
        List<Map<String, Object>> operations = (List<Map<String, Object>>) mapped.get("operations");
        List<Map<String, Object>> artifacts = (List<Map<String, Object>>) mapped.get("artifacts");

        assertNotNull(operations);
        assertNotNull(artifacts);
        assertEquals("地图查询完成", operations.get(0).get("title"));
        assertEquals("completed", operations.get(0).get("state"));
        assertEquals("guide", artifacts.get(0).get("type"));
        assertEquals("附近推荐", artifacts.get(0).get("title"));
    }

    private record FakeAgentService(List<AiMessage> messages) implements AgentService {
        @Override
        public AiConversation createConversation(Long userId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<AiConversation> listConversations(Long userId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<AiMessage> getMessages(Long userId, Long conversationId) {
            return messages;
        }

        @Override
        public void deleteConversation(Long userId, Long conversationId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public AiMessage sendMessage(Long userId, Long conversationId, String userMessage) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<AiMemory> getMemories(Long userId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public void deleteMemory(Long userId, Long memoryId) {
            throw new UnsupportedOperationException();
        }
    }
}
