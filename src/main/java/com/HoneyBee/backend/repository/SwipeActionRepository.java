package com.HoneyBee.backend.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.HoneyBee.backend.model.SwipeAction;
import com.HoneyBee.backend.model.SwipeDecision;

public interface SwipeActionRepository extends JpaRepository<SwipeAction, Long> {

    List<SwipeAction> findBySwiperId(Long swiperId);

    Optional<SwipeAction> findBySwiperIdAndTargetId(Long swiperId, Long targetId);

    boolean existsBySwiperIdAndTargetIdAndDecision(Long swiperId, Long targetId, SwipeDecision decision);
}
