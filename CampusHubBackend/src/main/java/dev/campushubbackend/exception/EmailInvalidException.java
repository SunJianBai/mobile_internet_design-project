package dev.campushubbackend.exception;

public class EmailInvalidException extends BusinessException {
    public EmailInvalidException(String message) {
        super(ErrorCode.EMAIL_INVALID, message);
    }

    public EmailInvalidException(String message, Throwable cause) {
        super(ErrorCode.EMAIL_INVALID, message, cause);
    }
}
