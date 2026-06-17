package dev.campushubbackend.service.impl;

import dev.campushubbackend.entity.SystemSetting;
import dev.campushubbackend.enums.ContentStatus;
import dev.campushubbackend.exception.FileUploadFailedException;
import dev.campushubbackend.repository.SystemSettingRepository;
import dev.campushubbackend.service.SystemSettingService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class SystemSettingServiceImpl implements SystemSettingService {

    private static final String CONTENT_AUDIT_ENABLED = "contentAuditEnabled";
    private static final String ALLOW_PUBLIC_REGISTRATION = "allowPublicRegistration";
    private static final String MAX_UPLOAD_SIZE_MB = "maxUploadSizeMb";
    private static final int MAX_UPLOAD_SIZE_LIMIT_MB = 20;

    private final SystemSettingRepository systemSettingRepository;

    @Override
    @Transactional(readOnly = true)
    public Map<String, Object> getSettings() {
        Map<String, Object> settings = defaultSettings();
        systemSettingRepository.findAll().forEach(item -> {
            if (settings.containsKey(item.getKey())) {
                settings.put(item.getKey(), parseSettingValue(item.getKey(), item.getValue()));
            }
        });
        return settings;
    }

    @Override
    @Transactional
    public Map<String, Object> updateSettings(Map<String, Object> settings) {
        if (settings == null || settings.isEmpty()) {
            return getSettings();
        }

        Map<String, Object> allowedSettings = defaultSettings();
        settings.forEach((key, value) -> {
            if (!allowedSettings.containsKey(key)) {
                return;
            }

            SystemSetting setting = systemSettingRepository.findById(key).orElseGet(SystemSetting::new);
            setting.setKey(key);
            setting.setValue(String.valueOf(sanitizeSettingValue(key, value)));
            setting.setLabel(settingLabels().get(key));
            setting.setGroupName(settingGroups().get(key));
            systemSettingRepository.save(setting);
        });

        return getSettings();
    }

    @Override
    @Transactional(readOnly = true)
    public boolean isPublicRegistrationAllowed() {
        return (Boolean) getSettings().get(ALLOW_PUBLIC_REGISTRATION);
    }

    @Override
    @Transactional(readOnly = true)
    public ContentStatus initialContentStatus() {
        return (Boolean) getSettings().get(CONTENT_AUDIT_ENABLED)
                ? ContentStatus.PENDING
                : ContentStatus.NORMAL;
    }

    @Override
    @Transactional(readOnly = true)
    public int getMaxUploadSizeMb() {
        return (Integer) getSettings().get(MAX_UPLOAD_SIZE_MB);
    }

    @Override
    @Transactional(readOnly = true)
    public void validateUploadSize(MultipartFile file) {
        if (file == null) {
            return;
        }

        int maxUploadSizeMb = getMaxUploadSizeMb();
        long maxBytes = maxUploadSizeMb * 1024L * 1024L;
        if (file.getSize() > maxBytes) {
            throw new FileUploadFailedException(
                    "文件大小超过后台设置上限: filename=" + file.getOriginalFilename()
                            + ", maxUploadSizeMb=" + maxUploadSizeMb
            );
        }
    }

    private Map<String, Object> defaultSettings() {
        Map<String, Object> defaults = new LinkedHashMap<>();
        defaults.put("compactTable", true);
        defaults.put("confirmActions", true);
        defaults.put("pageSize", 20);
        defaults.put(CONTENT_AUDIT_ENABLED, true);
        defaults.put(ALLOW_PUBLIC_REGISTRATION, true);
        defaults.put(MAX_UPLOAD_SIZE_MB, 20);
        defaults.put("maintenanceNotice", "");
        return defaults;
    }

    private Map<String, String> settingLabels() {
        Map<String, String> labels = new HashMap<>();
        labels.put("compactTable", "紧凑表格");
        labels.put("confirmActions", "危险操作二次确认");
        labels.put("pageSize", "默认分页大小");
        labels.put(CONTENT_AUDIT_ENABLED, "内容巡检开关");
        labels.put(ALLOW_PUBLIC_REGISTRATION, "开放用户注册");
        labels.put(MAX_UPLOAD_SIZE_MB, "最大上传大小");
        labels.put("maintenanceNotice", "维护公告");
        return labels;
    }

    private Map<String, String> settingGroups() {
        Map<String, String> groups = new HashMap<>();
        groups.put("compactTable", "后台偏好");
        groups.put("confirmActions", "后台偏好");
        groups.put("pageSize", "后台偏好");
        groups.put(CONTENT_AUDIT_ENABLED, "运维策略");
        groups.put(ALLOW_PUBLIC_REGISTRATION, "运维策略");
        groups.put(MAX_UPLOAD_SIZE_MB, "运维策略");
        groups.put("maintenanceNotice", "运维策略");
        return groups;
    }

    private Object sanitizeSettingValue(String key, Object value) {
        Object defaultValue = defaultSettings().get(key);
        if (defaultValue instanceof Boolean) {
            return Boolean.parseBoolean(String.valueOf(value));
        }
        if (defaultValue instanceof Integer) {
            int parsed = parseInteger(String.valueOf(value), (Integer) defaultValue);
            if ("pageSize".equals(key)) {
                return Math.min(Math.max(parsed, 10), 50);
            }
            if (MAX_UPLOAD_SIZE_MB.equals(key)) {
                return Math.min(Math.max(parsed, 1), MAX_UPLOAD_SIZE_LIMIT_MB);
            }
            return parsed;
        }
        return value == null ? "" : String.valueOf(value);
    }

    private Object parseSettingValue(String key, String value) {
        return sanitizeSettingValue(key, value);
    }

    private int parseInteger(String value, int fallback) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }
}
