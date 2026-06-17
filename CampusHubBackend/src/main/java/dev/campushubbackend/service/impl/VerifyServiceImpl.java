package dev.campushubbackend.service.impl;

import dev.campushubbackend.entity.VerifyCodeRecord;
import dev.campushubbackend.enums.VerifyCodeRecordStatus;
import dev.campushubbackend.enums.VerifyCodeRecordType;
import dev.campushubbackend.exception.UserExistException;
import dev.campushubbackend.exception.UserNotExistException;
import dev.campushubbackend.repository.UserRepository;
import dev.campushubbackend.entity.User;
import dev.campushubbackend.repository.VerifyCodeRecordRepository;
import dev.campushubbackend.service.SystemSettingService;
import dev.campushubbackend.service.VerifyService;
import dev.campushubbackend.exception.EmailInvalidException;
import dev.campushubbackend.exception.RegisterFailedException;
import dev.campushubbackend.utils.EmailTemplateUtil;
import dev.campushubbackend.utils.VerifyCodeUtil;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;


@Slf4j
@Service
@RequiredArgsConstructor
public class VerifyServiceImpl implements VerifyService {

    private final JavaMailSender mailSender;
    private final VerifyCodeRecordRepository verifyCodeRecordRepository;
    private final PasswordEncoder passwordEncoder;
    private final SystemSettingService systemSettingService;

    /**
     * 发件人邮箱地址，需与 spring.mail.username 保持一致
     */
    @Value("${spring.mail.username}")
    private String fromEmail;

    // 验证码有效期（分钟）
    private static final int EXPIRE_MINUTES = 5;


    @Transactional
    public void verifyEmail(String email, VerifyCodeRecordType type) throws EmailInvalidException, UserExistException {
        if (type == VerifyCodeRecordType.REGISTER && !systemSettingService.isPublicRegistrationAllowed()) {
            throw new RegisterFailedException("当前暂未开放公开注册");
        }

        String code = VerifyCodeUtil.generateCode6Num();
        LocalDateTime expireTime =
                LocalDateTime.now().plusMinutes(EXPIRE_MINUTES);
        String content = EmailTemplateUtil.buildVerifyCodeEmail(code, EXPIRE_MINUTES);
        sendEmail(email, "邮箱验证码", content);

        VerifyCodeRecord record = new VerifyCodeRecord();
        record.setEmail(email);
        record.setCode(passwordEncoder.encode(code));
        record.setType(type);
        record.setStatus(VerifyCodeRecordStatus.UNUSED);
        record.setExpiredAt(expireTime);
        verifyCodeRecordRepository.save(record);
        log.info("发送验证码: email={}, code={}", email, code);
    }


    /**
     * 发送邮件
     * @param to 收件邮箱
     * @param subject 标题
     * @param content 内容
     */
    private void sendEmail(String to, String subject, String content) throws EmailInvalidException {
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper =
                    new MimeMessageHelper(message, true, StandardCharsets.UTF_8.name());
            // 一些邮箱服务（如 163）要求 From 与认证账号一致，否则会报 553
            helper.setFrom(fromEmail);
            helper.setTo(to);
            helper.setSubject(subject);
            helper.setText(content, true);
            mailSender.send(message);
        } catch (MessagingException e) {
            throw new EmailInvalidException("无法发送邮件: email=" + to, e);
        }
    }
}

