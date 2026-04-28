package com.HoneyBee.backend.service;

import java.util.List;

import org.springframework.stereotype.Service;

import com.HoneyBee.backend.dto.UserProfileRequest;
import com.HoneyBee.backend.model.UserProfile;
import com.HoneyBee.backend.repository.UserProfileRepository;

@Service
public class UserProfileService {

    private final UserProfileRepository userProfileRepository;

    public UserProfileService(UserProfileRepository userProfileRepository) {
        this.userProfileRepository = userProfileRepository;
    }

    public UserProfile createUserProfile(UserProfileRequest request) {
        UserProfile userProfile = new UserProfile();
        userProfile.setFullName(request.fullName());
        userProfile.setEmail(request.email());
        userProfile.setUsername(request.username());
        userProfile.setCity(request.city());
        userProfile.setAge(request.age());
        userProfile.setBirthDate(request.birthDate());
        userProfile.setGender(request.gender());
        userProfile.setRelationshipGoal(request.relationshipGoal());
        userProfile.setBio(request.bio());
        userProfile.setProfilePhotoUrl(request.profilePhotoUrl());
        return userProfileRepository.save(userProfile);
    }

    public List<UserProfile> getAllProfiles() {
        return userProfileRepository.findAll();
    }

    public UserProfile getProfile(Long id) {
        return userProfileRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("User profile not found for id " + id));
    }
}
