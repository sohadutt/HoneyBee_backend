package com.HoneyBee.backend.dto;

import com.HoneyBee.backend.model.DatingPreference;
import com.HoneyBee.backend.model.Gender;

public record DatingPreferenceView(
        Long id,
        Gender interestedIn,
        Integer minPreferredAge,
        Integer maxPreferredAge) {

    public static DatingPreferenceView from(DatingPreference preference) {
        return new DatingPreferenceView(
                preference.getId(),
                preference.getInterestedIn(),
                preference.getMinPreferredAge(),
                preference.getMaxPreferredAge());
    }
}
