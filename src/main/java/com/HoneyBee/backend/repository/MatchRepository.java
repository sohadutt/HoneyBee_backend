package com.HoneyBee.backend.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import com.HoneyBee.backend.model.Match;

public interface MatchRepository extends JpaRepository<Match, Long> {

    List<Match> findByUserOneIdOrUserTwoIdOrderByMatchedAtDesc(Long userOneId, Long userTwoId);

    boolean existsByUserOneIdAndUserTwoId(Long userOneId, Long userTwoId);

    boolean existsByUserOneIdAndUserTwoIdOrUserOneIdAndUserTwoId(
            Long userOneId,
            Long userTwoId,
            Long reverseUserOneId,
            Long reverseUserTwoId);
}
