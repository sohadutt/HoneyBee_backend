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

import com.HoneyBee.backend.dto.UserProfileRequest;
import com.HoneyBee.backend.dto.UserProfileView;
import com.HoneyBee.backend.service.UserProfileService;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/profiles")
public class UserProfileController {

    private final UserProfileService userProfileService;

    public UserProfileController(UserProfileService userProfileService) {
        this.userProfileService = userProfileService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public UserProfileView createProfile(@Valid @RequestBody UserProfileRequest request) {
        return UserProfileView.from(userProfileService.createUserProfile(request));
    }

    @GetMapping
    public List<UserProfileView> getAllProfiles() {
        return userProfileService.getAllProfiles().stream()
                .map(UserProfileView::from)
                .toList();
    }

    @GetMapping("/{id}")
    public UserProfileView getProfile(@PathVariable Long id) {
        return UserProfileView.from(userProfileService.getProfile(id));
    }
}
