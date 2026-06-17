package dev.campushubbackend.exception;

public class UserBannedException extends BusinessException {

    public UserBannedException(String message) {
        super(ErrorCode.NO_PERMISSION, message);
    }

    public UserBannedException(String message, Throwable cause) {
        super(ErrorCode.NO_PERMISSION, message, cause);
    }
}
