package dev.campushubbackend.exception;

public class OrderExpiredException extends BusinessException {
    public OrderExpiredException(String message) {
        super(ErrorCode.ORDER_EXPIRED, message);
    }

    public OrderExpiredException(String message, Throwable cause) {
        super(ErrorCode.ORDER_EXPIRED, message, cause);
    }
}
