package dev.campushubbackend.exception;

public class UserExistException extends BusinessException {
    public UserExistException(String message) {
        super(ErrorCode.USER_EXISTS, message);
    }

    public UserExistException(String message, Throwable cause) {
        super(ErrorCode.USER_EXISTS, message, cause);
    }
}
