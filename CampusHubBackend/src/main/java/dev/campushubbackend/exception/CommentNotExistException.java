package dev.campushubbackend.exception;

public class CommentNotExistException extends BusinessException {
    public CommentNotExistException(String message) {
        super(ErrorCode.COMMENT_NOT_EXIST, message);
    }

    public CommentNotExistException(String message, Throwable cause) {
        super(ErrorCode.COMMENT_NOT_EXIST, message, cause);
    }
}
