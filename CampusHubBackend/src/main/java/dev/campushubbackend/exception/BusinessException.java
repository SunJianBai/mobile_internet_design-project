package dev.campushubbackend.exception;

public abstract class BusinessException extends RuntimeException {
    private final ErrorCode errorCode;

    public BusinessException(String message, Throwable cause) {
        this(ErrorCode.BAD_REQUEST, message, cause);
    }

    public BusinessException(String message) {
        this(ErrorCode.BAD_REQUEST, message);
    }

    protected BusinessException(ErrorCode errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }

    protected BusinessException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public int getCode(){
        return errorCode.getCode();
    }

    public String getCodeType(){
        return errorCode.getMessage();
    }
}
