from __future__ import annotations

import heapq
from dataclasses import dataclass

from django.db.models import Q, QuerySet

from .models import User
from .obj import Dominance, Orientation, Sex


@dataclass(frozen=True)
class Recommendation:
    user: User
    score: int
    shared_kinks: list[str]
    dominance_score: int
    orientation_score: int


# Mapping of which roles are naturally complementary to one another
COMPLEMENTARY_DOMINANCE: dict[str, set[str]] = {
    Dominance.DOMINANT: {Dominance.SUBMISSIVE, Dominance.BOTTOM, Dominance.SWITCH},
    Dominance.SUBMISSIVE: {Dominance.DOMINANT, Dominance.TOP, Dominance.SWITCH},
    Dominance.TOP: {Dominance.BOTTOM, Dominance.SUBMISSIVE, Dominance.SWITCH},
    Dominance.BOTTOM: {Dominance.TOP, Dominance.DOMINANT, Dominance.SWITCH},
    Dominance.SWITCH: {
        Dominance.DOMINANT,
        Dominance.SUBMISSIVE,
        Dominance.TOP,
        Dominance.BOTTOM,
        Dominance.SWITCH,
    },
    Dominance.OTHER: {Dominance.OTHER, Dominance.SWITCH},
}


def recommend_users(user: User, limit: int = 20) -> list[Recommendation]:
    """
    Retrieves and scores the top recommended users for a given user.
    Optimized to pre-calculate user states and utilize heap sorting.
    """
    # 1. Pre-calculate the evaluating user's traits exactly ONCE.
    # Because kinks are now a JSON list of strings, we just convert the list to a set directly
    user_kinks = set(user.kinks if isinstance(user.kinks, list) else [])
    user_roles = set(user.dominance if isinstance(user.dominance, list) else [])
    preferred_roles = set(user.match_dominance_preferences if isinstance(user.match_dominance_preferences, list) else [])
    
    complementary_roles = {
        candidate_role
        for user_role in user_roles
        for candidate_role in COMPLEMENTARY_DOMINANCE.get(user_role, set())
    }

    # 2. Fetch only viable candidates from the database
    candidates = _get_viable_candidates(user)

    # 3. Score all viable candidates
    scored_candidates = [
        _score_candidate(user, candidate, user_kinks, preferred_roles, complementary_roles)
        for candidate in candidates
    ]

    # 4. Use heapq to find the top N results in O(N log K) time
    return heapq.nlargest(limit, scored_candidates, key=lambda item: item.score)


def _get_viable_candidates(user: User) -> QuerySet[User]:
    """
    Filters out completely incompatible users at the database level to drastically
    reduce the size of the QuerySet loaded into Python memory.
    """
    query = User.objects.exclude(pk=user.pk).filter(is_active=True, is_verified=True)

    # Optimization: Filter out biologically/identifiably incompatible orientations
    if user.orientation == Orientation.STRAIGHT:
        query = query.exclude(sex=user.sex).exclude(
            orientation__in=[Orientation.GAY, Orientation.LESBIAN]
        )
    elif user.orientation == Orientation.GAY and user.sex == Sex.MALE:
        query = query.filter(sex=Sex.MALE).exclude(orientation=Orientation.STRAIGHT)
    elif user.orientation == Orientation.LESBIAN and user.sex == Sex.FEMALE:
        query = query.filter(sex=Sex.FEMALE).exclude(orientation=Orientation.STRAIGHT)

    # No prefetch_related needed anymore since kinks are stored in a JSONField directly on the user!
    return query


def _score_candidate(
    user: User, 
    candidate: User, 
    user_kinks: set[str], 
    preferred_roles: set[str], 
    complementary_roles: set[str]
) -> Recommendation:
    """Calculates the compatibility score using pre-computed user datasets."""
    
    # Kink Score (Directly from the JSON array)
    candidate_kinks = set(candidate.kinks if isinstance(candidate.kinks, list) else [])
    shared_kinks = sorted(user_kinks & candidate_kinks)
    kink_score = min(len(shared_kinks) * 12, 48)

    # Dominance Score
    candidate_roles = set(candidate.dominance if isinstance(candidate.dominance, list) else [])
    preference_overlap = preferred_roles & candidate_roles
    compatibility_overlap = complementary_roles & candidate_roles
    dominance_score = min((len(preference_overlap) * 14) + (len(compatibility_overlap) * 10), 28)

    # Orientation & Verification Score
    orientation_score = _orientation_score(user, candidate)
    verification_score = 5 if candidate.highres_pictures_urls else 0

    # Total bounded to 100
    score = min(kink_score + dominance_score + orientation_score + verification_score, 100)

    return Recommendation(
        user=candidate,
        score=score,
        shared_kinks=shared_kinks,
        dominance_score=dominance_score,
        orientation_score=orientation_score,
    )


def _orientation_score(user: User, candidate: User) -> int:
    """Scores orientation based on mutual compatibility."""
    
    if user.orientation in {Orientation.PANSEXUAL, Orientation.BISEXUAL, Orientation.QUEER}:
        return 19
        
    if user.orientation == Orientation.ASEXUAL:
        return 10

    if user.orientation == Orientation.STRAIGHT:
        return 19 if _binary_opposite(user.sex, candidate.sex) else 0
        
    if user.orientation == Orientation.GAY:
        return 19 if user.sex == Sex.MALE and candidate.sex == Sex.MALE else 0
        
    if user.orientation == Orientation.LESBIAN:
        return 19 if user.sex == Sex.FEMALE and candidate.sex == Sex.FEMALE else 0
        
    return 12


def _binary_opposite(user_sex: str, candidate_sex: str) -> bool:
    """Checks if two sexes form a strict male/female binary opposite."""
    return {user_sex, candidate_sex} == {Sex.MALE, Sex.FEMALE}