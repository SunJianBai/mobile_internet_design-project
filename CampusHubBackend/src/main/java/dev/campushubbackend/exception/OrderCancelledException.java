package dev.campushubbackend.exception;

public class OrderCancelledException extends BusinessException {
    public OrderCancelledException(String message) {
        super(ErrorCode.ORDER_CANCELLED, message);
    }

    public OrderCancelledException(String message, Throwable cause) {
        super(ErrorCode.ORDER_CANCELLED, message, cause);
    }
}
