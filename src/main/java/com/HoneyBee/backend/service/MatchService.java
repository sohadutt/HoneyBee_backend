package com.HoneyBee.backend.service;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;

import org.springframework.stereotype.Service;

import com.HoneyBee.backend.model.Match;
import com.HoneyBee.backend.model.UserProfile;
import com.HoneyBee.backend.repository.MatchRepository;

@Service
public class MatchService {

    private final MatchRepository matchRepository;

    public MatchService(MatchRepository matchRepository) {
        this.matchRepository = matchRepository;
    }

    public Match createIfMissing(UserProfile firstUser, UserProfile secondUser) {
        Long smallerId = Math.min(firstUser.getId(), secondUser.getId());
        Long largerId = Math.max(firstUser.getId(), secondUser.getId());

        if (matchRepository.existsByUserOneIdAndUserTwoIdOrUserOneIdAndUserTwoId(
                smallerId,
                largerId,
                largerId,
                smallerId)) {
            return matchRepository.findByUserOneIdOrUserTwoIdOrderByMatchedAtDesc(smallerId, largerId).stream()
                    .filter(match -> containsUsers(match, smallerId, largerId))
                    .max(Comparator.comparing(Match::getMatchedAt))
                    .orElseThrow();
        }

        Match match = new Match();
        match.setUserOne(firstUser.getId().equals(smallerId) ? firstUser : secondUser);
        match.setUserTwo(firstUser.getId().equals(largerId) ? firstUser : secondUser);
        match.setMatchedAt(LocalDateTime.now());
        return matchRepository.save(match);
    }

    public List<Match> getMatchesForUser(Long userId) {
        return matchRepository.findByUserOneIdOrUserTwoIdOrderByMatchedAtDesc(userId, userId);
    }

    private boolean containsUsers(Match match, Long firstUserId, Long secondUserId) {
        return match.getUserOne().getId().equals(firstUserId) && match.getUserTwo().getId().equals(secondUserId)
                || match.getUserOne().getId().equals(secondUserId) && match.getUserTwo().getId().equals(firstUserId);
    }
}
