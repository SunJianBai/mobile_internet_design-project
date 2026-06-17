package dev.campushubbackend.exception;

public class ParamValidationFailedException extends BusinessException {
    public ParamValidationFailedException(String message) {
        super(ErrorCode.PARAM_VALIDATION_FAILED, message);
    }

    public ParamValidationFailedException(String message, Throwable cause) {
        super(ErrorCode.PARAM_VALIDATION_FAILED, message, cause);
    }
}
