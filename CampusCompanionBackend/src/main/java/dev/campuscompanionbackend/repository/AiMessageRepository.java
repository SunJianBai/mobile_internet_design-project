package dev.campuscompanionbackend.repository;

import dev.campuscompanionbackend.entity.AiConversation;
import dev.campuscompanionbackend.entity.AiMessage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface AiMessageRepository extends JpaRepository<AiMessage, Long> {

    List<AiMessage> findByConversationOrderByCreatedAtAsc(AiConversation conversation);

    void deleteByConversation(AiConversation conversation);
}
