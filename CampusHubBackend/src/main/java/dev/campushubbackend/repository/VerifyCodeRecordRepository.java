package dev.campushubbackend.repository;

import dev.campushubbackend.entity.User;
import dev.campushubbackend.entity.VerifyCodeRecord;
import dev.campushubbackend.enums.VerifyCodeRecordStatus;
import dev.campushubbackend.enums.VerifyCodeRecordType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;


@Repository
public interface VerifyCodeRecordRepository extends JpaRepository<VerifyCodeRecord, Long> {

    Optional<VerifyCodeRecord> findFirstByEmailAndTypeAndStatusOrderByCreatedAtDesc(
            String email,
            VerifyCodeRecordType type,
            VerifyCodeRecordStatus status
    );
}
