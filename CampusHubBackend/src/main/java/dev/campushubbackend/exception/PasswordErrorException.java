package dev.campushubbackend.exception;

public class PasswordErrorException extends BusinessException {
    public PasswordErrorException(String message) {
        super(ErrorCode.PASSWORD_ERROR, message);
    }

    public PasswordErrorException(String message, Throwable cause) {
        super(ErrorCode.PASSWORD_ERROR, message, cause);
    }
}
