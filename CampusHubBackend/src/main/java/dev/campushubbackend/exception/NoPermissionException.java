package dev.campushubbackend.exception;

public class NoPermissionException extends BusinessException {
    public NoPermissionException(String message) {
        super(ErrorCode.NO_PERMISSION, message);
    }

    public NoPermissionException(String message, Throwable cause) {
        super(ErrorCode.NO_PERMISSION, message, cause);
    }
}
