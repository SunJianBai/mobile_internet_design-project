package dev.campushubbackend.exception;

public class FileUploadFailedException extends BusinessException {
    public FileUploadFailedException(String message) {
        super(ErrorCode.FILE_UPLOAD_FAILED, message);
    }

    public FileUploadFailedException(String message, Throwable cause) {
        super(ErrorCode.FILE_UPLOAD_FAILED, message, cause);
    }
}
