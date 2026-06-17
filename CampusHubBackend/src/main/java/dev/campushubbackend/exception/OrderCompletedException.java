package dev.campushubbackend.exception;

public class OrderCompletedException extends BusinessException {
    public OrderCompletedException(String message) {
        super(ErrorCode.ORDER_COMPLETED, message);
    }

    public OrderCompletedException(String message, Throwable cause) {
        super(ErrorCode.ORDER_COMPLETED, message, cause);
    }
}
