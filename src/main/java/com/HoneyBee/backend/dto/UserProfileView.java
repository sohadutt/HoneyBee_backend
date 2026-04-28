package com.HoneyBee.backend.dto;

import java.time.LocalDate;

import com.HoneyBee.backend.model.Gender;
import com.HoneyBee.backend.model.RelationshipGoal;
import com.HoneyBee.backend.model.UserProfile;

public record UserProfileView(
        Long id,
        String fullName,
        String username,
        String email,
        String city,
        Integer age,
        LocalDate birthDate,
        Gender gender,
        RelationshipGoal relationshipGoal,
        String bio,
        String profilePhotoUrl) {

    public static UserProfileView from(UserProfile userProfile) {
        return new UserProfileView(
                userProfile.getId(),
                userProfile.getFullName(),
                userProfile.getUsername(),
                userProfile.getEmail(),
                userProfile.getCity(),
                userProfile.getAge(),
                userProfile.getBirthDate(),
                userProfile.getGender(),
                userProfile.getRelationshipGoal(),
                userProfile.getBio(),
                userProfile.getProfilePhotoUrl());
    }
}
