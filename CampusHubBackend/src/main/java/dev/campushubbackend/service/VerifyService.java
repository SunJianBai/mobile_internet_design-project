package dev.campushubbackend.service;


import dev.campushubbackend.enums.VerifyCodeRecordType;
import dev.campushubbackend.exception.EmailInvalidException;
import dev.campushubbackend.exception.UserExistException;

public interface VerifyService {

    /**
     * 验证邮箱
     *
     * @param email the email
     * @throws EmailInvalidException the email verify exception
     */
    void verifyEmail(String email, VerifyCodeRecordType type) throws EmailInvalidException, UserExistException;
}
