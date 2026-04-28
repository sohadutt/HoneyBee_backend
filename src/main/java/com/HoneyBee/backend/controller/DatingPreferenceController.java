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

import com.HoneyBee.backend.dto.DatingPreferenceRequest;
import com.HoneyBee.backend.dto.DatingPreferenceView;
import com.HoneyBee.backend.service.DatingPreferenceService;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/profiles/{userId}/preferences")
public class DatingPreferenceController {

    private final DatingPreferenceService datingPreferenceService;

    public DatingPreferenceController(DatingPreferenceService datingPreferenceService) {
        this.datingPreferenceService = datingPreferenceService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public DatingPreferenceView createPreference(
            @PathVariable Long userId,
            @Valid @RequestBody DatingPreferenceRequest request) {
        return DatingPreferenceView.from(datingPreferenceService.addPreference(userId, request));
    }

    @GetMapping
    public List<DatingPreferenceView> getPreferences(@PathVariable Long userId) {
        return datingPreferenceService.getPreferences(userId).stream()
                .map(DatingPreferenceView::from)
                .toList();
    }
}
