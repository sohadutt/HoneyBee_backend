package com.HoneyBee.backend.model;

import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "dating_preferences")
public class DatingPreference {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false)
    @JoinColumn(name = "user_profile_id")
    private UserProfile userProfile;

    @Enumerated(EnumType.STRING)
    private Gender interestedIn;

    private Integer minPreferredAge;

    private Integer maxPreferredAge;

    public DatingPreference() {
    }

    public Long getId() {
        return id;
    }

    public UserProfile getUserProfile() {
        return userProfile;
    }

    public void setUserProfile(UserProfile userProfile) {
        this.userProfile = userProfile;
    }

    public Gender getInterestedIn() {
        return interestedIn;
    }

    public void setInterestedIn(Gender interestedIn) {
        this.interestedIn = interestedIn;
    }

    public Integer getMinPreferredAge() {
        return minPreferredAge;
    }

    public void setMinPreferredAge(Integer minPreferredAge) {
        this.minPreferredAge = minPreferredAge;
    }

    public Integer getMaxPreferredAge() {
        return maxPreferredAge;
    }

    public void setMaxPreferredAge(Integer maxPreferredAge) {
        this.maxPreferredAge = maxPreferredAge;
    }
}
