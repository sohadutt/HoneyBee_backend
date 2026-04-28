package com.HoneyBee.backend.dto;

import com.HoneyBee.backend.model.Gender;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record DatingPreferenceRequest(
        @NotNull Gender interestedIn,
        @Min(18) @Max(100) Integer minPreferredAge,
        @Min(18) @Max(100) Integer maxPreferredAge) {
}
