package com.HoneyBee.backend.dto;

import com.HoneyBee.backend.model.SwipeDecision;

public record SwipeResultView(
        Long swipeId,
        Long swiperId,
        Long targetId,
        SwipeDecision decision,
        boolean matched,
        MatchView match) {
}
