package com.HoneyBee.backend.controller;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.HoneyBee.backend.dto.MatchView;
import com.HoneyBee.backend.dto.SwipeRequest;
import com.HoneyBee.backend.dto.SwipeResultView;
import com.HoneyBee.backend.dto.UserProfileView;
import com.HoneyBee.backend.service.MatchService;
import com.HoneyBee.backend.service.SwipeService;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api")
public class SwipeController {

    private final SwipeService swipeService;
    private final MatchService matchService;

    public SwipeController(SwipeService swipeService, MatchService matchService) {
        this.swipeService = swipeService;
        this.matchService = matchService;
    }

    @GetMapping("/profiles/{userId}/discover")
    public List<UserProfileView> discoverProfiles(@PathVariable Long userId) {
        return swipeService.browseProfiles(userId).stream()
                .map(UserProfileView::from)
                .toList();
    }

    @PostMapping("/swipes")
    @ResponseStatus(HttpStatus.CREATED)
    public SwipeResultView swipe(@Valid @RequestBody SwipeRequest request) {
        return swipeService.swipe(request);
    }

    @GetMapping("/profiles/{userId}/matches")
    public List<MatchView> getMatches(@PathVariable Long userId) {
        return matchService.getMatchesForUser(userId).stream()
                .map(match -> MatchView.from(match, userId))
                .toList();
    }
}
