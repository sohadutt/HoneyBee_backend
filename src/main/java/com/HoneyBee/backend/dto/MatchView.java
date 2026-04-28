package com.HoneyBee.backend.dto;

import java.time.LocalDateTime;

import com.HoneyBee.backend.model.Match;
import com.HoneyBee.backend.model.UserProfile;

public record MatchView(
        Long matchId,
        Long currentUserId,
        UserProfileView otherUser,
        LocalDateTime matchedAt) {

    public static MatchView from(Match match, Long currentUserId) {
        UserProfile otherUser = match.getUserOne().getId().equals(currentUserId)
                ? match.getUserTwo()
                : match.getUserOne();

        return new MatchView(match.getId(), currentUserId, UserProfileView.from(otherUser), match.getMatchedAt());
    }
}
