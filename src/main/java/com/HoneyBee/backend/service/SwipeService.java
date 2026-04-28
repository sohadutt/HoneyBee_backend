package com.HoneyBee.backend.service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.HoneyBee.backend.dto.SwipeRequest;
import com.HoneyBee.backend.dto.SwipeResultView;
import com.HoneyBee.backend.dto.MatchView;
import com.HoneyBee.backend.model.Match;
import com.HoneyBee.backend.model.SwipeAction;
import com.HoneyBee.backend.model.SwipeDecision;
import com.HoneyBee.backend.model.UserProfile;
import com.HoneyBee.backend.repository.SwipeActionRepository;

@Service
public class SwipeService {

    private final SwipeActionRepository swipeActionRepository;
    private final UserProfileService userProfileService;
    private final MatchService matchService;

    public SwipeService(
            SwipeActionRepository swipeActionRepository,
            UserProfileService userProfileService,
            MatchService matchService) {
        this.swipeActionRepository = swipeActionRepository;
        this.userProfileService = userProfileService;
        this.matchService = matchService;
    }

    public List<UserProfile> browseProfiles(Long userId) {
        userProfileService.getProfile(userId);
        Set<Long> alreadySeenIds = swipeActionRepository.findBySwiperId(userId).stream()
                .map(action -> action.getTarget().getId())
                .collect(Collectors.toSet());

        return userProfileService.getAllProfiles().stream()
                .filter(profile -> !profile.getId().equals(userId))
                .filter(profile -> !alreadySeenIds.contains(profile.getId()))
                .toList();
    }

    public SwipeResultView swipe(SwipeRequest request) {
        if (request.swiperId().equals(request.targetId())) {
            throw new IllegalArgumentException("Users cannot swipe on themselves");
        }

        UserProfile swiper = userProfileService.getProfile(request.swiperId());
        UserProfile target = userProfileService.getProfile(request.targetId());

        SwipeAction action = swipeActionRepository.findBySwiperIdAndTargetId(swiper.getId(), target.getId())
                .orElseGet(SwipeAction::new);
        action.setSwiper(swiper);
        action.setTarget(target);
        action.setDecision(request.decision());
        action.setCreatedAt(LocalDateTime.now());
        SwipeAction savedAction = swipeActionRepository.save(action);

        boolean isMutualLike = request.decision() == SwipeDecision.LIKE
                && swipeActionRepository.existsBySwiperIdAndTargetIdAndDecision(
                        target.getId(),
                        swiper.getId(),
                        SwipeDecision.LIKE);

        MatchView matchView = null;
        if (isMutualLike) {
            Match match = matchService.createIfMissing(swiper, target);
            matchView = MatchView.from(match, swiper.getId());
        }

        return new SwipeResultView(
                savedAction.getId(),
                swiper.getId(),
                target.getId(),
                request.decision(),
                isMutualLike,
                matchView);
    }
}
