package dev.campushubbackend.exception;

public class OrderFullException extends BusinessException{
    public OrderFullException(String message) {
        super(ErrorCode.ORDER_FULL, message);
    }

    public OrderFullException(String message, Throwable cause) {
        super(ErrorCode.ORDER_FULL, message, cause);
    }
}
