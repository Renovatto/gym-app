"""Painel administrativo: operacao de contas e metricas de uso.

Tres regras que valem para o arquivo inteiro:

1. **So comportamento, nunca conteudo de saude.** O admin ve se a pessoa lancou
   refeicao, treinou e quando - nunca peso, gordura, IMC ou fase do ciclo. Peso e
   composicao corporal sao dado sensivel, e nada aqui precisa deles para operar.
2. **Paginacao no servidor.** Toda listagem devolve `{items, total, page,
   page_size}`; `total` sai da MESMA clausula where da consulta, so que contada.
   O cliente nunca recebe a base inteira para cortar no navegador.
3. **Metrica derivada do banco.** Nada aqui depende de coletar evento de uso novo -
   "quem esta usando" sai do que ja existe (lancamentos, treinos, pesagens). Tela
   aberta e tempo de uso ficam para a etapa propria de eventos.

Siglas: BIA = bioimpedancia; nao aparece aqui de proposito (ver a regra 1).
"""

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, union_all
from sqlmodel import Session, col, func, select

from ..config import settings
from ..deps import AdminUser, SessionDep
from ..models import (
    Connection,
    ConnectionStatus,
    CycleTracking,
    DiaryEntry,
    NewsItem,
    NewsRead,
    Objective,
    PasswordResetToken,
    Profile,
    User,
    WeightLog,
    WorkoutSession,
    utcnow,
)
from ..schemas import (
    AdminActivityPoint,
    AdminActivitySeries,
    AdminNewsRow,
    AdminNewsWrite,
    AdminObjectiveSlice,
    AdminOverview,
    AdminUserDetail,
    AdminUserPage,
    AdminUserRow,
)
from ..services.email import send_password_reset_email
from ..services.text import normalize_search

router = APIRouter(prefix="/admin", tags=["admin"])

# Ordenacoes aceitas na listagem. Lista fechada de proposito: sort e string vinda
# da URL, e mapear para coluna evita transformar o parametro em injecao de SQL.
_SORT_COLUMNS = {"email", "created_at", "last_activity"}


def _activity_subquery():
    """Uma linha (user_id, happened_at) por acao registrada pelo usuario.

    Lancamento de refeicao, treino e pesagem entram na mesma pilha porque a
    pergunta do painel e "esta usando o app?", nao "usou qual tela". Da pesagem
    entra so o CARIMBO DE TEMPO - o valor pesado nunca sai daqui.
    """
    return union_all(
        select(
            col(DiaryEntry.user_id).label("user_id"),
            col(DiaryEntry.logged_at).label("happened_at"),
        ),
        select(
            col(WorkoutSession.user_id).label("user_id"),
            col(WorkoutSession.started_at).label("happened_at"),
        ),
        select(
            col(WeightLog.user_id).label("user_id"),
            col(WeightLog.logged_at).label("happened_at"),
        ),
    ).subquery()


def _last_activity_subquery():
    """Ultima atividade de cada usuario, seja de que tipo for."""
    activity = _activity_subquery()
    return (
        select(
            activity.c.user_id.label("user_id"),
            func.max(activity.c.happened_at).label("last_at"),
        )
        .group_by(activity.c.user_id)
        .subquery()
    )


def _matching_user_ids(session: Session, term: str) -> list[int]:
    """IDs cujo nome ou e-mail casam com o termo, comparando SEM acento e SEM caixa.

    A comparacao acontece em Python porque `normalize_search` precisa rodar dos DOIS
    lados (regra do projeto) e nem SQLite nem Postgres sem extensao sabem remover
    acento no meio da consulta. O custo e uma varredura de tres colunas leves; a
    paginacao continua 100% no servidor, porque o resultado vira um `IN (...)` na
    consulta paginada. Se a base crescer a ponto de doer, o caminho e uma coluna
    normalizada em profiles - nao trazer a lista inteira para o cliente.
    """
    needle = normalize_search(term)
    rows = session.exec(
        select(User.id, User.email, Profile.first_name, Profile.last_name).join(
            Profile, col(Profile.user_id) == col(User.id), isouter=True
        )
    ).all()
    matched: list[int] = []
    for user_id, email, first_name, last_name in rows:
        haystack = " ".join(part for part in (email, first_name, last_name) if part)
        if needle in normalize_search(haystack):
            matched.append(user_id)
    return matched


def _full_name(profile: Profile | None) -> str | None:
    if profile is None:
        return None
    parts = [part for part in (profile.first_name, profile.last_name) if part]
    return " ".join(parts) if parts else None


def _days_since(moment: datetime | None) -> int | None:
    if moment is None:
        return None
    # Datas antigas podem voltar sem fuso do SQLite; assume UTC para nao estourar
    # na subtracao entre aware e naive.
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0, (utcnow() - moment).days)


def _count_of(statement: Select) -> Select:
    """Transforma a consulta da pagina na contagem do total, mantendo where e joins."""
    return select(func.count()).select_from(statement.subquery())


@router.get("/users", response_model=AdminUserPage)
def list_users(
    admin: AdminUser,
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, description="nome ou e-mail, sem acento e sem caixa"),
    objective: Objective | None = Query(default=None),
    active_within_days: int | None = Query(default=None, ge=1, le=365),
    inactive_for_days: int | None = Query(default=None, ge=1, le=365),
    signed_up_within_days: int | None = Query(default=None, ge=1, le=3650),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> AdminUserPage:
    if sort not in _SORT_COLUMNS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="INVALID_SORT")

    last_activity = _last_activity_subquery()
    base = (
        select(User, Profile, last_activity.c.last_at)
        .join(Profile, col(Profile.user_id) == col(User.id), isouter=True)
        .join(last_activity, last_activity.c.user_id == col(User.id), isouter=True)
    )

    if q and q.strip():
        matched = _matching_user_ids(session, q.strip())
        if not matched:
            # Nenhum candidato: devolve a pagina vazia sem ir ao banco de novo.
            return AdminUserPage(items=[], total=0, page=page, page_size=page_size)
        base = base.where(col(User.id).in_(matched))

    if objective is not None:
        base = base.where(col(Profile.objective) == objective)

    if active_within_days is not None:
        cutoff = utcnow() - timedelta(days=active_within_days)
        base = base.where(last_activity.c.last_at >= cutoff)

    if inactive_for_days is not None:
        # Inativo inclui quem nunca registrou nada: sem essa metade a lista mentiria
        # justamente sobre quem mais interessa procurar.
        cutoff = utcnow() - timedelta(days=inactive_for_days)
        base = base.where(
            (last_activity.c.last_at < cutoff) | (last_activity.c.last_at.is_(None))
        )

    if signed_up_within_days is not None:
        cutoff = utcnow() - timedelta(days=signed_up_within_days)
        base = base.where(col(User.created_at) >= cutoff)

    total = session.exec(_count_of(base)).one()

    sort_column = {
        "email": col(User.email),
        "created_at": col(User.created_at),
        "last_activity": last_activity.c.last_at,
    }[sort]
    ordered = base.order_by(
        sort_column.desc() if order == "desc" else sort_column.asc()
    )
    rows = session.exec(ordered.offset((page - 1) * page_size).limit(page_size)).all()

    items = [
        AdminUserRow(
            id=user.id,
            email=user.email,
            name=_full_name(profile),
            objective=profile.objective if profile else None,
            plan=user.plan,
            diet_enabled=profile.diet_enabled if profile else False,
            created_at=user.created_at,
            last_activity_at=last_at,
            days_since_activity=_days_since(last_at),
        )
        for user, profile, last_at in rows
    ]
    return AdminUserPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user(user_id: int, admin: AdminUser, session: SessionDep) -> AdminUserDetail:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")

    profile = session.exec(
        select(Profile).where(col(Profile.user_id) == user_id)
    ).first()
    cycle = session.exec(
        select(CycleTracking).where(col(CycleTracking.user_id) == user_id)
    ).first()

    since = utcnow() - timedelta(days=30)
    meals_30d = session.exec(
        select(func.count())
        .select_from(DiaryEntry)
        .where(col(DiaryEntry.user_id) == user_id, col(DiaryEntry.logged_at) >= since)
    ).one()
    workouts_30d = session.exec(
        select(func.count())
        .select_from(WorkoutSession)
        .where(
            col(WorkoutSession.user_id) == user_id,
            col(WorkoutSession.started_at) >= since,
        )
    ).one()
    weigh_ins_30d = session.exec(
        select(func.count())
        .select_from(WeightLog)
        .where(col(WeightLog.user_id) == user_id, col(WeightLog.logged_at) >= since)
    ).one()
    connections = session.exec(
        select(func.count())
        .select_from(Connection)
        .where(
            col(Connection.status) == ConnectionStatus.accepted,
            (col(Connection.requester_user_id) == user_id)
            | (col(Connection.addressee_user_id) == user_id),
        )
    ).one()

    last_activity = _last_activity_subquery()
    last_at = session.exec(
        select(last_activity.c.last_at).where(last_activity.c.user_id == user_id)
    ).first()

    return AdminUserDetail(
        id=user.id,
        email=user.email,
        name=_full_name(profile),
        objective=profile.objective if profile else None,
        plan=user.plan,
        locale=user.locale,
        diet_enabled=profile.diet_enabled if profile else False,
        # So o liga/desliga do acompanhamento: fase e datas nunca saem para o painel.
        cycle_enabled=bool(cycle and cycle.enabled),
        created_at=user.created_at,
        last_activity_at=last_at,
        days_since_activity=_days_since(last_at),
        meals_30d=meals_30d,
        workouts_30d=workouts_30d,
        weigh_ins_30d=weigh_ins_30d,
        connections=connections,
    )


@router.post("/users/{user_id}/password-reset", status_code=status.HTTP_204_NO_CONTENT)
def send_reset_link(user_id: int, admin: AdminUser, session: SessionDep) -> None:
    """Dispara o mesmo e-mail do "esqueci minha senha", a pedido do admin.

    Rede de seguranca para quem nao recebe o proprio e-mail: o admin nunca escolhe a
    senha nova, so provoca o envio do link. A senha atual continua valendo ate o link
    ser usado, e o token expira igual ao do fluxo normal.
    """
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")

    # Mesmo formato do fluxo publico (auth.forgot_password): token de uso unico.
    token = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(minutes=settings.password_reset_minutes)
    session.add(
        PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    )
    session.commit()
    send_password_reset_email(user.email, token, user.locale)


@router.get("/metrics/overview", response_model=AdminOverview)
def overview(admin: AdminUser, session: SessionDep) -> AdminOverview:
    now = utcnow()
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    total_users = session.exec(select(func.count()).select_from(User)).one()
    new_users_7d = session.exec(
        select(func.count()).select_from(User).where(col(User.created_at) >= last_7d)
    ).one()
    new_users_30d = session.exec(
        select(func.count()).select_from(User).where(col(User.created_at) >= last_30d)
    ).one()

    # Ativo = registrou QUALQUER coisa na janela. Conta distinta de usuario, nao de
    # acao: quem lancou 40 refeicoes na semana continua sendo uma pessoa ativa.
    activity = _activity_subquery()
    active_7d = session.exec(
        select(func.count(func.distinct(activity.c.user_id))).where(
            activity.c.happened_at >= last_7d
        )
    ).one()
    active_30d = session.exec(
        select(func.count(func.distinct(activity.c.user_id))).where(
            activity.c.happened_at >= last_30d
        )
    ).one()

    meals_7d = session.exec(
        select(func.count())
        .select_from(DiaryEntry)
        .where(col(DiaryEntry.logged_at) >= last_7d)
    ).one()
    workouts_7d = session.exec(
        select(func.count())
        .select_from(WorkoutSession)
        .where(col(WorkoutSession.started_at) >= last_7d)
    ).one()
    diet_enabled_users = session.exec(
        select(func.count()).select_from(Profile).where(col(Profile.diet_enabled))
    ).one()

    objective_rows = session.exec(
        select(col(Profile.objective), func.count()).group_by(col(Profile.objective))
    ).all()
    objectives = [
        AdminObjectiveSlice(objective=objective, users=users)
        for objective, users in objective_rows
    ]

    return AdminOverview(
        total_users=total_users,
        new_users_7d=new_users_7d,
        new_users_30d=new_users_30d,
        active_7d=active_7d,
        active_30d=active_30d,
        meals_7d=meals_7d,
        workouts_7d=workouts_7d,
        diet_enabled_users=diet_enabled_users,
        objectives=objectives,
    )


@router.get("/metrics/activity", response_model=AdminActivitySeries)
def activity_series(
    admin: AdminUser,
    session: SessionDep,
    days: int = Query(default=30, ge=7, le=180),
) -> AdminActivitySeries:
    """Serie diaria de usuarios ativos, refeicoes e treinos.

    Os dias sem nenhum registro tambem voltam, com zero: uma serie temporal com
    buracos vira mentira no grafico, porque a linha liga dois pontos distantes como
    se nada tivesse acontecido entre eles.
    """
    start_day = (utcnow() - timedelta(days=days - 1)).date()
    since = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)

    activity = _activity_subquery()
    active_rows = session.exec(
        select(
            func.date(activity.c.happened_at).label("day"),
            func.count(func.distinct(activity.c.user_id)),
        )
        .where(activity.c.happened_at >= since)
        .group_by(func.date(activity.c.happened_at))
    ).all()
    meal_rows = session.exec(
        select(func.date(col(DiaryEntry.logged_at)), func.count())
        .where(col(DiaryEntry.logged_at) >= since)
        .group_by(func.date(col(DiaryEntry.logged_at)))
    ).all()
    workout_rows = session.exec(
        select(func.date(col(WorkoutSession.started_at)), func.count())
        .where(col(WorkoutSession.started_at) >= since)
        .group_by(func.date(col(WorkoutSession.started_at)))
    ).all()

    def by_day(rows: list[tuple]) -> dict[date, int]:
        # func.date devolve str no SQLite e date no Postgres; normaliza para date.
        out: dict[date, int] = {}
        for day, count in rows:
            out[date.fromisoformat(day) if isinstance(day, str) else day] = count
        return out

    actives, meals, workouts = by_day(active_rows), by_day(meal_rows), by_day(workout_rows)
    points = [
        AdminActivityPoint(
            day=start_day + timedelta(days=offset),
            active_users=actives.get(start_day + timedelta(days=offset), 0),
            meals=meals.get(start_day + timedelta(days=offset), 0),
            workouts=workouts.get(start_day + timedelta(days=offset), 0),
        )
        for offset in range(days)
    ]
    return AdminActivitySeries(days=days, points=points)


# --- Novidades do app ---
#
# Diferente do resto deste arquivo, aqui o admin ESCREVE conteudo que os usuarios veem.
# Duas consequencias: os seis textos (titulo e corpo nos 3 idiomas) sao obrigatorios,
# para nao existir novidade que apareca vazia para quem usa em ingles ou espanhol; e
# despublicar existe separado de excluir, porque tirar do ar e reversivel e apagar nao.


def _news_row(session: Session, item: NewsItem) -> AdminNewsRow:
    read_count = session.exec(
        select(func.count()).select_from(NewsRead).where(NewsRead.news_id == item.id)
    ).one()
    return AdminNewsRow(
        id=item.id,
        published_on=item.published_on,
        importance=item.importance,
        published=item.published,
        title_pt_br=item.title_pt_br,
        body_pt_br=item.body_pt_br,
        title_en=item.title_en,
        body_en=item.body_en,
        title_es=item.title_es,
        body_es=item.body_es,
        created_at=item.created_at,
        read_count=read_count,
    )


@router.get("/news", response_model=list[AdminNewsRow])
def list_news(admin: AdminUser, session: SessionDep) -> list[AdminNewsRow]:
    """Todas as novidades, publicadas ou nao. Sem paginacao: sao poucas por natureza -
    se um dia passarem de uma centena, entra a paginacao padrao do arquivo."""
    items = session.exec(
        select(NewsItem).order_by(
            col(NewsItem.published_on).desc(), col(NewsItem.id).desc()
        )
    ).all()
    return [_news_row(session, item) for item in items]


@router.post("/news", response_model=AdminNewsRow, status_code=status.HTTP_201_CREATED)
def create_news(data: AdminNewsWrite, admin: AdminUser, session: SessionDep) -> AdminNewsRow:
    item = NewsItem(**data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return _news_row(session, item)


@router.put("/news/{news_id}", response_model=AdminNewsRow)
def update_news(
    news_id: int, data: AdminNewsWrite, admin: AdminUser, session: SessionDep
) -> AdminNewsRow:
    item = session.get(NewsItem, news_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="NEWS_NOT_FOUND")
    for campo, valor in data.model_dump().items():
        setattr(item, campo, valor)
    session.add(item)
    session.commit()
    session.refresh(item)
    return _news_row(session, item)


@router.delete("/news/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_news(news_id: int, admin: AdminUser, session: SessionDep) -> None:
    """Apaga a novidade e, por cascata, as marcas de leitura dela. Irreversivel - para
    so tirar do ar, o caminho e published=false no update."""
    item = session.get(NewsItem, news_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="NEWS_NOT_FOUND")
    session.delete(item)
    session.commit()
