"""Revisao do registro alimentar e refeicoes aproximadas, isoladas do diario legado."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ..deps import CurrentUser, SessionDep
from ..models import DiaryDayReview, DiaryEstimate, utcnow
from ..schemas import DiaryEstimateIn, DiaryEstimateOut, DiaryReviewIn, DiaryReviewOut
from ..services.diary_tracking import estimate_out, load_day_record

router = APIRouter(prefix="/me/diary-records", tags=["diet"])


def validate_day(day: date, today: date) -> None:
    if day > today:
        raise HTTPException(400, detail="DIARY_FUTURE_DAY")


@router.put("/{day}/review", response_model=DiaryReviewOut)
def review_day(
    day: date, payload: DiaryReviewIn, user: CurrentUser, session: SessionDep,
    today: date = Query(...),
) -> DiaryReviewOut:
    validate_day(day, today)
    record = load_day_record(session, user.id, day)
    if payload.fingerprint != record.fingerprint:
        raise HTTPException(409, detail="DIARY_CHANGED")
    if payload.status == "complete":
        if record.has_unknown_energy:
            raise HTTPException(400, detail="DIARY_UNKNOWN_ENERGY")
        if not record.has_record and not payload.consumed_nothing:
            raise HTTPException(400, detail="DIARY_EMPTY_CONFIRM")
    review = record.review or DiaryDayReview(user_id=user.id, entry_date=day)
    review.status = payload.status
    review.entries_fingerprint = record.fingerprint
    review.reviewed_at = utcnow()
    session.add(review)
    session.commit()
    record.review = review
    return record.review_out()


def apply_estimate(estimate: DiaryEstimate, payload: DiaryEstimateIn) -> None:
    name = payload.name.strip()
    reference = (payload.reference or "").strip() or None
    if not name:
        raise HTTPException(400, detail="ESTIMATE_NAME_REQUIRED")
    if payload.kcal_per_portion is not None and reference is None:
        raise HTTPException(400, detail="ESTIMATE_REFERENCE_REQUIRED")
    estimate.entry_date = payload.entry_date
    estimate.meal_type = payload.meal_type
    estimate.name = name
    estimate.portions = payload.portions
    estimate.kcal_per_portion = payload.kcal_per_portion
    estimate.reference = reference


@router.post("/estimates", response_model=DiaryEstimateOut, status_code=201)
def add_estimate(
    payload: DiaryEstimateIn, user: CurrentUser, session: SessionDep,
    today: date = Query(...),
) -> DiaryEstimateOut:
    validate_day(payload.entry_date, today)
    estimate = DiaryEstimate(user_id=user.id)
    apply_estimate(estimate, payload)
    session.add(estimate)
    session.commit()
    session.refresh(estimate)
    return estimate_out(estimate)


def owned_estimate(session: SessionDep, user_id: int, estimate_id: int) -> DiaryEstimate:
    estimate = session.get(DiaryEstimate, estimate_id)
    if estimate is None or estimate.user_id != user_id:
        raise HTTPException(404, detail="ENTRY_NOT_FOUND")
    return estimate


@router.put("/estimates/{estimate_id}", response_model=DiaryEstimateOut)
def update_estimate(
    estimate_id: int, payload: DiaryEstimateIn, user: CurrentUser, session: SessionDep,
    today: date = Query(...),
) -> DiaryEstimateOut:
    estimate = owned_estimate(session, user.id, estimate_id)
    validate_day(payload.entry_date, today)
    apply_estimate(estimate, payload)
    session.add(estimate)
    session.commit()
    session.refresh(estimate)
    return estimate_out(estimate)


@router.delete("/estimates/{estimate_id}", status_code=204)
def delete_estimate(estimate_id: int, user: CurrentUser, session: SessionDep) -> None:
    session.delete(owned_estimate(session, user.id, estimate_id))
    session.commit()
