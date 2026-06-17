package dev.campushubbackend.exception;

public class RegisterFailedException extends BusinessException {
    public RegisterFailedException(String message) {
        super(ErrorCode.REGISTER_FAILED, message);
    }

    public RegisterFailedException(String message, Throwable cause) {
        super(ErrorCode.REGISTER_FAILED, message, cause);
    }
}
