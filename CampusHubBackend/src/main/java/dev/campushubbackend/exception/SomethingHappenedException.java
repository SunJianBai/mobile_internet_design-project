package dev.campushubbackend.exception;

public class SomethingHappenedException extends BusinessException {
    public SomethingHappenedException(String message) {
        super(ErrorCode.SOMETHING_HAPPENED, message);
    }

    public SomethingHappenedException(String message, Throwable cause) {
        super(ErrorCode.SOMETHING_HAPPENED, message, cause);
    }
}
