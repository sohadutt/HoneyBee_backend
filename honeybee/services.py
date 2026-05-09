from __future__ import annotations

import heapq
from dataclasses import dataclass

from django.db.models import Prefetch, Q, QuerySet

from .models import Kink, User


@dataclass(frozen=True)
class Recommendation:
    user: User
    score: int
    shared_kinks: list[str]
    dominance_score: int
    orientation_score: int


# Mapping of which roles are naturally complementary to one another
COMPLEMENTARY_DOMINANCE: dict[str, set[str]] = {
    User.Dominance.DOMINANT: {User.Dominance.SUBMISSIVE, User.Dominance.BOTTOM, User.Dominance.SWITCH},
    User.Dominance.SUBMISSIVE: {User.Dominance.DOMINANT, User.Dominance.TOP, User.Dominance.SWITCH},
    User.Dominance.TOP: {User.Dominance.BOTTOM, User.Dominance.SUBMISSIVE, User.Dominance.SWITCH},
    User.Dominance.BOTTOM: {User.Dominance.TOP, User.Dominance.DOMINANT, User.Dominance.SWITCH},
    User.Dominance.SWITCH: {
        User.Dominance.DOMINANT,
        User.Dominance.SUBMISSIVE,
        User.Dominance.TOP,
        User.Dominance.BOTTOM,
        User.Dominance.SWITCH,
    },
    User.Dominance.OTHER: {User.Dominance.OTHER, User.Dominance.SWITCH},
}


def recommend_users(user: User, limit: int = 20) -> list[Recommendation]:
    """
    Retrieves and scores the top recommended users for a given user.
    Optimized to pre-calculate user states and utilize heap sorting.
    """
    # 1. Pre-calculate the evaluating user's traits exactly ONCE.
    user_kinks = set(kink.name for kink in user.kinks.all())
    user_roles = set(user.dominance or [])
    preferred_roles = set(user.match_dominance_preferences or [])
    
    complementary_roles = {
        candidate_role
        for user_role in user_roles
        for candidate_role in COMPLEMENTARY_DOMINANCE.get(user_role, set())
    }

    # 2. Fetch only viable candidates from the database (saves memory/compute)
    candidates = _get_viable_candidates(user)

    # 3. Score all viable candidates
    scored_candidates = [
        _score_candidate(user, candidate, user_kinks, preferred_roles, complementary_roles)
        for candidate in candidates
    ]

    # 4. Use heapq to find the top N results in O(N log K) time instead of O(N log N) sort
    return heapq.nlargest(limit, scored_candidates, key=lambda item: item.score)


def _get_viable_candidates(user: User) -> QuerySet[User]:
    """
    Filters out completely incompatible users at the database level to drastically
    reduce the size of the QuerySet loaded into Python memory.
    """
    query = User.objects.exclude(pk=user.pk).filter(is_active=True, is_verified=True)

    # Optimization: Filter out biologically/identifiably incompatible orientations
    if user.orientation == User.Orientation.STRAIGHT:
        # Exclude same sex and strictly homosexual candidates
        query = query.exclude(sex=user.sex).exclude(
            orientation__in=[User.Orientation.GAY, User.Orientation.LESBIAN]
        )
    elif user.orientation == User.Orientation.GAY and user.sex == User.Sex.MALE:
        # Strictly look for other men, exclude strictly straight men
        query = query.filter(sex=User.Sex.MALE).exclude(orientation=User.Orientation.STRAIGHT)
    elif user.orientation == User.Orientation.LESBIAN and user.sex == User.Sex.FEMALE:
        # Strictly look for other women, exclude strictly straight women
        query = query.filter(sex=User.Sex.FEMALE).exclude(orientation=User.Orientation.STRAIGHT)

    # Prefetch kinks for the remaining valid subset
    return query.prefetch_related(Prefetch("kinks", queryset=Kink.objects.only("name")))


def _score_candidate(
    user: User, 
    candidate: User, 
    user_kinks: set[str], 
    preferred_roles: set[str], 
    complementary_roles: set[str]
) -> Recommendation:
    """Calculates the compatibility score using pre-computed user datasets."""
    
    # Kink Score
    candidate_kinks = set(kink.name for kink in candidate.kinks.all())
    shared_kinks = sorted(user_kinks & candidate_kinks)
    kink_score = min(len(shared_kinks) * 12, 48)

    # Dominance Score
    candidate_roles = set(candidate.dominance or [])
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
    
    # Highly fluid orientations grant max score inherently
    if user.orientation in {User.Orientation.PANSEXUAL, User.Orientation.BISEXUAL, User.Orientation.QUEER}:
        return 19
        
    if user.orientation == User.Orientation.ASEXUAL:
        return 10

    # Strict binary matching rules (Note: DB already filtered worst mismatches)
    if user.orientation == User.Orientation.STRAIGHT:
        return 19 if _binary_opposite(user.sex, candidate.sex) else 0
        
    if user.orientation == User.Orientation.GAY:
        return 19 if user.sex == User.Sex.MALE and candidate.sex == User.Sex.MALE else 0
        
    if user.orientation == User.Orientation.LESBIAN:
        return 19 if user.sex == User.Sex.FEMALE and candidate.sex == User.Sex.FEMALE else 0
        
    return 12


def _binary_opposite(user_sex: str, candidate_sex: str) -> bool:
    """Checks if two sexes form a strict male/female binary opposite."""
    return {user_sex, candidate_sex} == {User.Sex.MALE, User.Sex.FEMALE}