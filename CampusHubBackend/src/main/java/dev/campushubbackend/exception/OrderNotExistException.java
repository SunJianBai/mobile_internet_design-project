package dev.campushubbackend.exception;

public class OrderNotExistException extends BusinessException {
    public OrderNotExistException(String message) {
        super(ErrorCode.ORDER_NOT_EXIST, message);
    }

    public OrderNotExistException(String message, Throwable cause) {
        super(ErrorCode.ORDER_NOT_EXIST, message, cause);
    }
}
