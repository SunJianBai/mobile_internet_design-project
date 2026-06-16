package dev.campushubbackend.repository;

import dev.campushubbackend.entity.AiMemory;
import dev.campushubbackend.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface AiMemoryRepository extends JpaRepository<AiMemory, Long> {

    List<AiMemory> findByUserOrderByUpdatedAtDesc(User user);

    List<AiMemory> findByUserAndCategory(User user, String category);
}
