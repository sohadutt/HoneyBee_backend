from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Prefetch

from .models import Kink, User


@dataclass(frozen=True)
class Recommendation:
    user: User
    score: int
    shared_kinks: list[str]
    dominance_score: int
    orientation_score: int


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
    candidates = (
        User.objects.exclude(pk=user.pk)
        .filter(is_active=True, is_verified=True)
        .prefetch_related(Prefetch("kinks", queryset=Kink.objects.only("name")))
    )
    scored = [_score_candidate(user, candidate) for candidate in candidates]
    return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]


def _score_candidate(user: User, candidate: User) -> Recommendation:
    shared_kinks = sorted(set(_kink_names(user)) & set(_kink_names(candidate)))
    kink_score = min(len(shared_kinks) * 12, 48)
    dominance_score = _dominance_score(user, candidate)
    orientation_score = _orientation_score(user, candidate)
    verification_score = 5 if candidate.highres_pictures_urls else 0
    score = min(kink_score + dominance_score + orientation_score + verification_score, 100)
    return Recommendation(
        user=candidate,
        score=score,
        shared_kinks=shared_kinks,
        dominance_score=dominance_score,
        orientation_score=orientation_score,
    )


def _kink_names(user: User) -> list[str]:
    return [kink.name for kink in user.kinks.all()]


def _dominance_score(user: User, candidate: User) -> int:
    user_roles = set(user.dominance or [])
    candidate_roles = set(candidate.dominance or [])
    preferred_roles = set(user.match_dominance_preferences or [])

    preference_overlap = preferred_roles & candidate_roles
    complementary_roles = {
        candidate_role
        for user_role in user_roles
        for candidate_role in COMPLEMENTARY_DOMINANCE.get(user_role, set())
    }
    compatibility_overlap = complementary_roles & candidate_roles

    return min((len(preference_overlap) * 14) + (len(compatibility_overlap) * 10), 28)


def _orientation_score(user: User, candidate: User) -> int:
    if user.orientation in {User.Orientation.PANSEXUAL, User.Orientation.BISEXUAL, User.Orientation.QUEER}:
        return 19
    if user.orientation == User.Orientation.ASEXUAL:
        return 10
    if user.orientation == User.Orientation.STRAIGHT:
        return 19 if _binary_opposite(user.sex, candidate.sex) else 0
    if user.orientation == User.Orientation.GAY:
        return 19 if user.sex == User.Sex.MALE and candidate.sex == User.Sex.MALE else 0
    if user.orientation == User.Orientation.LESBIAN:
        return 19 if user.sex == User.Sex.FEMALE and candidate.sex == User.Sex.FEMALE else 0
    return 12


def _binary_opposite(user_sex: str, candidate_sex: str) -> bool:
    return {user_sex, candidate_sex} == {User.Sex.MALE, User.Sex.FEMALE}
