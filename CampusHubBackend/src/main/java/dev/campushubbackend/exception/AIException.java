package dev.campushubbackend.exception;

public class AIException extends BusinessException{
    public AIException(String message) {
        super(ErrorCode.AI_FAILED, message);
    }

    public AIException(String message, Throwable cause) {
        super(ErrorCode.AI_FAILED, message, cause);
    }

    public AIException(String message, ErrorCode errorCode) {
        super(errorCode, message);
    }

    public AIException(String message, Throwable cause, ErrorCode errorCode) {
        super(errorCode, message, cause);
    }
}
