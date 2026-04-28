package com.HoneyBee.backend.dto;

import com.HoneyBee.backend.model.SwipeDecision;

import jakarta.validation.constraints.NotNull;

public record SwipeRequest(
        @NotNull Long swiperId,
        @NotNull Long targetId,
        @NotNull SwipeDecision decision) {
}
