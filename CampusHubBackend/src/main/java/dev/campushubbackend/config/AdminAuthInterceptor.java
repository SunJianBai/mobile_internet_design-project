package dev.campushubbackend.config;

import dev.campushubbackend.entity.User;
import dev.campushubbackend.enums.UserStatus;
import dev.campushubbackend.enums.UserType;
import dev.campushubbackend.exception.ErrorCode;
import dev.campushubbackend.repository.UserRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Optional;

@Component
public class AdminAuthInterceptor implements HandlerInterceptor {

    private final UserRepository userRepository;

    public AdminAuthInterceptor(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }

        String userIdHeader = request.getHeader("X-User-Id");
        if (!StringUtils.hasText(userIdHeader)) {
            return writeError(response, HttpServletResponse.SC_UNAUTHORIZED, ErrorCode.UNAUTHORIZED.getCode(), "请先登录");
        }

        Long userId;
        try {
            userId = Long.parseLong(userIdHeader);
        } catch (NumberFormatException e) {
            return writeError(response, HttpServletResponse.SC_UNAUTHORIZED, ErrorCode.UNAUTHORIZED.getCode(), "登录状态无效");
        }

        Optional<User> userOptional = userRepository.findById(userId);
        if (userOptional.isEmpty()) {
            return writeError(response, HttpServletResponse.SC_UNAUTHORIZED, ErrorCode.UNAUTHORIZED.getCode(), "登录用户不存在");
        }

        User user = userOptional.get();
        if (UserStatus.BANNED.equals(user.getUserStatus())) {
            return writeError(response, HttpServletResponse.SC_FORBIDDEN, ErrorCode.FORBIDDEN.getCode(), "账号已被封禁");
        }

        if (!UserType.ADMIN.equals(user.getUserType())) {
            return writeError(response, HttpServletResponse.SC_FORBIDDEN, ErrorCode.FORBIDDEN.getCode(), "仅管理员可访问后台接口");
        }

        return true;
    }

    private boolean writeError(HttpServletResponse response, int status, int code, String message) throws IOException {
        response.setStatus(status);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write(String.format(
                "{\"code\":%d,\"message\":\"%s\",\"data\":null,\"timestamp\":%d}",
                code,
                escapeJson(message),
                System.currentTimeMillis()
        ));
        return false;
    }

    private String escapeJson(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
