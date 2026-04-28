package com.HoneyBee.backend.service;

import java.util.List;

import org.springframework.stereotype.Service;

import com.HoneyBee.backend.dto.DatingPreferenceRequest;
import com.HoneyBee.backend.model.DatingPreference;
import com.HoneyBee.backend.model.UserProfile;
import com.HoneyBee.backend.repository.DatingPreferenceRepository;

@Service
public class DatingPreferenceService {

    private final DatingPreferenceRepository datingPreferenceRepository;
    private final UserProfileService userProfileService;

    public DatingPreferenceService(
            DatingPreferenceRepository datingPreferenceRepository,
            UserProfileService userProfileService) {
        this.datingPreferenceRepository = datingPreferenceRepository;
        this.userProfileService = userProfileService;
    }

    public DatingPreference addPreference(Long userId, DatingPreferenceRequest request) {
        if (request.minPreferredAge() != null
                && request.maxPreferredAge() != null
                && request.minPreferredAge() > request.maxPreferredAge()) {
            throw new IllegalArgumentException("Minimum preferred age cannot be greater than maximum preferred age");
        }

        UserProfile userProfile = userProfileService.getProfile(userId);
        DatingPreference preference = new DatingPreference();
        preference.setUserProfile(userProfile);
        preference.setInterestedIn(request.interestedIn());
        preference.setMinPreferredAge(request.minPreferredAge());
        preference.setMaxPreferredAge(request.maxPreferredAge());
        return datingPreferenceRepository.save(preference);
    }

    public List<DatingPreference> getPreferences(Long userId) {
        userProfileService.getProfile(userId);
        return datingPreferenceRepository.findByUserProfileId(userId);
    }
}
