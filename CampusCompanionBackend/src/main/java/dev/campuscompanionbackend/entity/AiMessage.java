package dev.campuscompanionbackend.entity;

import jakarta.persistence.*;
import lombok.Data;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "ai_messages")
public class AiMessage {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long mid;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "cid", nullable = false)
    private AiConversation conversation;

    @Column(nullable = false, length = 20)
    private String role; // user, assistant, system, tool

    @Column(nullable = false, columnDefinition = "MEDIUMTEXT")
    private String content;

    @Column(length = 50)
    private String toolName; // 若为 tool 调用，记录工具名

    @Column
    private Integer tokenCount;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;
}
