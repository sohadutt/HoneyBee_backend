package com.HoneyBee.backend.dto;

import java.time.LocalDate;

import com.HoneyBee.backend.model.Gender;
import com.HoneyBee.backend.model.RelationshipGoal;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UserProfileRequest(
        @NotBlank @Size(max = 80) String fullName,
        @NotBlank @Email @Size(max = 120) String email,
        @NotBlank @Size(max = 40) String username,
        @Size(max = 120) String city,
        @Min(18) @Max(100) Integer age,
        LocalDate birthDate,
        Gender gender,
        RelationshipGoal relationshipGoal,
        @Size(max = 500) String bio,
        @Size(max = 255) String profilePhotoUrl) {
}
