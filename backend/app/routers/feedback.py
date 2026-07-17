"""Feedback / relato de problema. Qualquer usuario envia; so o admin (allowlist de
e-mail em settings.admin_emails) lista e marca como lido."""

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, desc, select

from ..deps import AdminUser, CurrentUser, SessionDep
from ..models import FeedbackReport, User
from ..schemas import FeedbackIn, FeedbackOut, FeedbackReadUpdate

router = APIRouter(prefix="/me/feedback", tags=["feedback"])


def _to_out(session: Session, report: FeedbackReport) -> FeedbackOut:
    author = session.get(User, report.user_id)
    return FeedbackOut(
        id=report.id,
        module=report.module,
        description=report.description,
        read=report.read,
        created_at=report.created_at,
        user_email=author.email if author else "?",
    )


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(data: FeedbackIn, user: CurrentUser, session: SessionDep) -> FeedbackOut:
    report = FeedbackReport(
        user_id=user.id, module=data.module, description=data.description.strip()
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return _to_out(session, report)


@router.get("/admin", response_model=list[FeedbackOut])
def list_feedback(admin: AdminUser, session: SessionDep) -> list[FeedbackOut]:
    """Todos os feedbacks, mais recentes primeiro (nao lidos e lidos misturados; o
    front destaca os nao lidos e mostra o contador)."""
    reports = session.exec(
        select(FeedbackReport).order_by(desc(FeedbackReport.created_at))
    ).all()
    return [_to_out(session, r) for r in reports]


@router.patch("/admin/{report_id}/read", response_model=FeedbackOut)
def set_feedback_read(
    report_id: int, data: FeedbackReadUpdate, admin: AdminUser, session: SessionDep
) -> FeedbackOut:
    report = session.get(FeedbackReport, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="FEEDBACK_NOT_FOUND")
    report.read = data.read
    session.add(report)
    session.commit()
    session.refresh(report)
    return _to_out(session, report)
