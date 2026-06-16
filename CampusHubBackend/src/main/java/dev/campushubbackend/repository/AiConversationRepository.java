package dev.campushubbackend.repository;

import dev.campushubbackend.entity.AiConversation;
import dev.campushubbackend.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface AiConversationRepository extends JpaRepository<AiConversation, Long> {

    List<AiConversation> findByUserOrderByUpdatedAtDesc(User user);

    Optional<AiConversation> findByCidAndUser(Long cid, User user);

    void deleteByUserAndCid(User user, Long cid);
}
