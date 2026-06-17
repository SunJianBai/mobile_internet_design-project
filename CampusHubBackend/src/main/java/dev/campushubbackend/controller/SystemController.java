package dev.campushubbackend.controller;

import dev.campushubbackend.dto.response.ApiResponse;
import dev.campushubbackend.service.SystemSettingService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Public system information APIs.
 */
@RestController
@RequestMapping("/api/v1/system")
public class SystemController extends BaseController {

    private final SystemSettingService systemSettingService;

    @Autowired
    public SystemController(SystemSettingService systemSettingService) {
        this.systemSettingService = systemSettingService;
    }

    @GetMapping("/public-info")
    public ApiResponse<Map<String, Object>> getPublicInfo() {
        Map<String, Object> settings = systemSettingService.getSettings();
        Map<String, Object> publicInfo = new LinkedHashMap<>();
        publicInfo.put("maintenanceNotice", settings.getOrDefault("maintenanceNotice", ""));
        return success(publicInfo);
    }
}
