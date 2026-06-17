package dev.campushubbackend.exception;

public class DuplicateOperationException extends BusinessException {
    public DuplicateOperationException(String message) {
        super(ErrorCode.DUPLICATE_OPERATION, message);
    }

    public DuplicateOperationException(String message, Throwable cause) {
        super(ErrorCode.DUPLICATE_OPERATION, message, cause);
    }
}
