package dev.campushubbackend.controller;

import dev.campushubbackend.dto.response.ApiResponse;
import dev.campushubbackend.enums.VerifyCodeRecordType;
import dev.campushubbackend.exception.UserExistException;
import dev.campushubbackend.service.VerifyService;
import dev.campushubbackend.exception.EmailInvalidException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/verify")
public class VerifyController extends BaseController{

    private final VerifyService verifyService;

    @Autowired
    public VerifyController(VerifyService verifyService) {
        this.verifyService = verifyService;
    }

    @PostMapping("/email/{email}")
    public ApiResponse<Void> verifyEmail(@PathVariable String email) throws EmailInvalidException, UserExistException {
        verifyService.verifyEmail(email, VerifyCodeRecordType.REGISTER);
        return ApiResponse.success(String.format("已向 %s 发送验证码", email), null);
    }
}
