package dev.campushubbackend.exception;

public class UserNotExistException extends BusinessException {
    public UserNotExistException(String message) {
        super(ErrorCode.USER_NOT_EXIST, message);
    }

    public UserNotExistException(String message, Throwable cause) {
        super(ErrorCode.USER_NOT_EXIST, message, cause);
    }
}
