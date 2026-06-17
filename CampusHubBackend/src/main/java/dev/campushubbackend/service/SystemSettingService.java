package dev.campushubbackend.service;

import dev.campushubbackend.enums.ContentStatus;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

public interface SystemSettingService {

    Map<String, Object> getSettings();

    Map<String, Object> updateSettings(Map<String, Object> settings);

    boolean isPublicRegistrationAllowed();

    ContentStatus initialContentStatus();

    int getMaxUploadSizeMb();

    void validateUploadSize(MultipartFile file);
}
