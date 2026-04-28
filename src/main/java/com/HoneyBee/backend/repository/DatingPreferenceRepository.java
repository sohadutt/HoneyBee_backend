package com.HoneyBee.backend.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import com.HoneyBee.backend.model.DatingPreference;

public interface DatingPreferenceRepository extends JpaRepository<DatingPreference, Long> {

    List<DatingPreference> findByUserProfileId(Long userProfileId);
}
