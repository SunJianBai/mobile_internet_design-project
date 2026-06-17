package dev.campushubbackend.exception;

public class ApplicationNotExistException extends BusinessException {
    public ApplicationNotExistException(String message) {
        super(ErrorCode.APPLICATION_NOT_EXIST, message);
    }

    public ApplicationNotExistException(String message, Throwable cause) {
        super(ErrorCode.APPLICATION_NOT_EXIST, message, cause);
    }
}
