package com.HoneyBee.backend.model;

import java.time.LocalDateTime;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "matches")
public class Match {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(optional = false)
    @JoinColumn(name = "user_one_id")
    private UserProfile userOne;

    @ManyToOne(optional = false)
    @JoinColumn(name = "user_two_id")
    private UserProfile userTwo;

    private LocalDateTime matchedAt;

    public Match() {
    }

    public Long getId() {
        return id;
    }

    public UserProfile getUserOne() {
        return userOne;
    }

    public void setUserOne(UserProfile userOne) {
        this.userOne = userOne;
    }

    public UserProfile getUserTwo() {
        return userTwo;
    }

    public void setUserTwo(UserProfile userTwo) {
        this.userTwo = userTwo;
    }

    public LocalDateTime getMatchedAt() {
        return matchedAt;
    }

    public void setMatchedAt(LocalDateTime matchedAt) {
        this.matchedAt = matchedAt;
    }
}
