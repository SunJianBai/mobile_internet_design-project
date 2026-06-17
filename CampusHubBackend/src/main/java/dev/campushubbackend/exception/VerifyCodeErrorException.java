package dev.campushubbackend.exception;

public class VerifyCodeErrorException extends BusinessException {
    public VerifyCodeErrorException(String message) {
        super(ErrorCode.VERIFY_CODE_ERROR, message);
    }

    public VerifyCodeErrorException(String message, Throwable cause) {
        super(ErrorCode.VERIFY_CODE_ERROR, message, cause);
    }
}
