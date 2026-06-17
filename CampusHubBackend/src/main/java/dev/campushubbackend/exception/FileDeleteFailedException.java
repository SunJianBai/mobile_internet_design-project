package dev.campushubbackend.exception;

public class FileDeleteFailedException extends BusinessException {
    public FileDeleteFailedException(String message) {
        super(ErrorCode.FILE_DELETE_FAILED, message);
    }

    public FileDeleteFailedException(String message, Throwable cause) {
        super(ErrorCode.FILE_DELETE_FAILED, message, cause);
    }
}
