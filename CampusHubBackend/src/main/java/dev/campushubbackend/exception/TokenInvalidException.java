package dev.campushubbackend.exception;

public class TokenInvalidException extends BusinessException {
    public TokenInvalidException(String message) {
        super(ErrorCode.TOKEN_INVALID, message);
    }

    public TokenInvalidException(String message, Throwable cause) {
        super(ErrorCode.TOKEN_INVALID, message, cause);
    }
}
