package com.HoneyBee.backend.model;

import java.time.LocalDateTime;

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
@Table(name = "swipe_actions")
public class SwipeAction {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false)
    @JoinColumn(name = "swiper_id")
    private UserProfile swiper;

    @ManyToOne(optional = false)
    @JoinColumn(name = "target_id")
    private UserProfile target;

    @Enumerated(EnumType.STRING)
    private SwipeDecision decision;

    private LocalDateTime createdAt;

    public SwipeAction() {
    }

    public Long getId() {
        return id;
    }

    public UserProfile getSwiper() {
        return swiper;
    }

    public void setSwiper(UserProfile swiper) {
        this.swiper = swiper;
    }

    public UserProfile getTarget() {
        return target;
    }

    public void setTarget(UserProfile target) {
        this.target = target;
    }

    public SwipeDecision getDecision() {
        return decision;
    }

    public void setDecision(SwipeDecision decision) {
        this.decision = decision;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }
}
