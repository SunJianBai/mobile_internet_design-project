package dev.campushubbackend.service.impl;

import dev.campushubbackend.entity.AiMemory;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AgentServiceMemoryPolicyTest {

    @Test
    void rejectsTransientMapDraftAndCoordinateMemories() {
        List<Map<String, String>> extracted = List.of(
                Map.of("category", "fact", "content", "用户提供的地点坐标为 116.170492, 39.728167"),
                Map.of("category", "behavior", "content", "用户正在寻找适合三人一起去的按摩店"),
                Map.of("category", "fact", "content", "用户想基于景阳阁SPA会所创建约伴订单草稿")
        );

        List<Map<String, String>> kept = AgentServiceImpl.filterAutoExtractedMemories(
                extracted,
                List.of(),
                "我想要找3个人一起去洗脚按摩，有什么推荐的店吗",
                "我找到了 3 家店，并准备了一个约伴订单草稿。"
        );

        assertTrue(kept.isEmpty());
    }

    @Test
    void keepsDurablePreferenceAndNormalizesCategory() {
        List<Map<String, String>> kept = AgentServiceImpl.filterAutoExtractedMemories(
                List.of(Map.of("category", "偏好", "content", "用户喜欢在良乡校区打篮球")),
                List.of(),
                "以后帮我优先推荐良乡校区的篮球活动",
                "好的，我会记住你的偏好。"
        );

        assertEquals(1, kept.size());
        assertEquals("preference", kept.getFirst().get("category"));
        assertEquals("用户喜欢在良乡校区打篮球", kept.getFirst().get("content"));
    }

    @Test
    void keepsStablePersonalFact() {
        List<Map<String, String>> kept = AgentServiceImpl.filterAutoExtractedMemories(
                List.of(Map.of("category", "fact", "content", "用户是计算机学院大三学生")),
                List.of(),
                "我是计算机学院大三学生，以后推荐活动可以考虑这个背景",
                "好的，我会记住。"
        );

        assertEquals(1, kept.size());
        assertEquals("fact", kept.getFirst().get("category"));
    }

    @Test
    void deduplicatesSimilarExistingMemory() {
        AiMemory existing = new AiMemory();
        existing.setCategory("preference");
        existing.setContent("用户偏好户外运动");

        List<Map<String, String>> kept = AgentServiceImpl.filterAutoExtractedMemories(
                List.of(Map.of("category", "preference", "content", "用户倾向于进行户外运动")),
                List.of(existing),
                "我比较喜欢户外运动",
                "好的，我会记住。"
        );

        assertTrue(kept.isEmpty());
    }

    @Test
    void capsAutoMemoriesPerTurn() {
        List<Map<String, String>> kept = AgentServiceImpl.filterAutoExtractedMemories(
                List.of(
                        Map.of("category", "preference", "content", "用户喜欢羽毛球"),
                        Map.of("category", "preference", "content", "用户偏好安静自习"),
                        Map.of("category", "behavior", "content", "用户经常晚上跑步")
                ),
                List.of(),
                "我喜欢羽毛球，也偏好安静自习，经常晚上跑步",
                "好的，我会记住这些偏好。"
        );

        assertEquals(AgentServiceImpl.MAX_AUTO_MEMORIES_PER_TURN, kept.size());
    }

    @Test
    void keepsConfirmedMemoryWithoutDurableKeyword() {
        List<Map<String, String>> kept = AgentServiceImpl.filterCommittedMemoryOperations(
                List.of(Map.of(
                        "operation", "save",
                        "category", "preference",
                        "content", "用户不吃辣"
                )),
                List.of()
        );

        assertEquals(1, kept.size());
        assertEquals("save", kept.getFirst().get("operation"));
        assertEquals("preference", kept.getFirst().get("category"));
        assertEquals("用户不吃辣", kept.getFirst().get("content"));
    }

    @Test
    void supportsConfirmedMemoryDeleteOperation() {
        List<Map<String, String>> kept = AgentServiceImpl.filterCommittedMemoryOperations(
                List.of(Map.of(
                        "operation", "delete",
                        "category", "preference",
                        "content", "用户不吃辣"
                )),
                List.of()
        );

        assertEquals(1, kept.size());
        assertEquals("delete", kept.getFirst().get("operation"));
    }

    @Test
    void confirmedMemorySaveStillRejectsDuplicatesAndCoordinates() {
        AiMemory existing = new AiMemory();
        existing.setCategory("preference");
        existing.setContent("用户不吃辣");

        List<Map<String, String>> kept = AgentServiceImpl.filterCommittedMemoryOperations(
                List.of(
                        Map.of("operation", "save", "category", "preference", "content", "用户不吃辣"),
                        Map.of("operation", "save", "category", "fact", "content", "用户常去坐标 116.170492,39.728167")
                ),
                List.of(existing)
        );

        assertTrue(kept.isEmpty());
    }
}
