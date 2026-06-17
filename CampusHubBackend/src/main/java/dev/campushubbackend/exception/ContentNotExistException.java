package dev.campushubbackend.exception;

public class ContentNotExistException extends BusinessException {
    public ContentNotExistException(String message) {
        super(ErrorCode.CONTENT_NOT_EXIST, message);
    }

    public ContentNotExistException(String message, Throwable cause) {
        super(ErrorCode.CONTENT_NOT_EXIST, message, cause);
    }
}
