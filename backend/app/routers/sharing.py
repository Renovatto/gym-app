"""Conexao entre duas contas e compartilhamento de receita/alimento.

Fase 1 do social: convite mutuo por e-mail, oferta que espera aceite e copia no
aceite. Sem perfil publico, sem descoberta de pessoas - as duas ja se conhecem.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, desc, or_, select

from ..deps import CurrentUser, SessionDep
from ..models import (
    Connection,
    ConnectionStatus,
    Food,
    Profile,
    Recipe,
    ShareOffer,
    ShareOfferStatus,
    SharedItem,
    SharedItemKind,
    User,
)
from ..schemas import (
    ConnectionInviteIn,
    ConnectionOut,
    ReceivedItemOut,
    ShareOfferIn,
    ShareOfferOut,
)
from ..services.sharing import SourceItemGone, copy_food, copy_recipe

router = APIRouter(prefix="/me/sharing", tags=["sharing"])


def _display_name(session: Session, user_id: int) -> str:
    """Nome de quem esta do outro lado. Cai no e-mail quando a pessoa nao preencheu
    o perfil - melhor mostrar algo identificavel do que um espaco vazio."""
    profile = session.exec(select(Profile).where(Profile.user_id == user_id)).first()
    if profile is not None:
        full_name = " ".join(filter(None, [profile.first_name, profile.last_name])).strip()
        if full_name:
            return full_name
    user = session.get(User, user_id)
    return user.email if user is not None else ""


def _other_user_id(connection: Connection, user_id: int) -> int:
    if connection.requester_user_id == user_id:
        return connection.addressee_user_id
    return connection.requester_user_id


def _connection_out(session: Session, connection: Connection, user_id: int) -> ConnectionOut:
    other_id = _other_user_id(connection, user_id)
    other = session.get(User, other_id)
    return ConnectionOut(
        id=connection.id,
        person_name=_display_name(session, other_id),
        person_email=other.email if other is not None else "",
        status=connection.status,
        i_invited=connection.requester_user_id == user_id,
        created_at=connection.created_at,
    )


def _owned_connection(session: Session, connection_id: int, user_id: int) -> Connection:
    connection = session.get(Connection, connection_id)
    if connection is None or user_id not in (
        connection.requester_user_id,
        connection.addressee_user_id,
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="CONNECTION_NOT_FOUND")
    return connection


# --- Conexoes -------------------------------------------------------------


@router.get("/connections", response_model=list[ConnectionOut])
def list_connections(user: CurrentUser, session: SessionDep) -> list[ConnectionOut]:
    """Conexoes nos dois sentidos: as que voce pediu e as que pediram para voce."""
    connections = session.exec(
        select(Connection)
        .where(
            or_(
                Connection.requester_user_id == user.id,
                Connection.addressee_user_id == user.id,
            )
        )
        .order_by(desc(Connection.created_at))
    ).all()
    return [_connection_out(session, c, user.id) for c in connections]


@router.post("/connections", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
def invite_connection(
    data: ConnectionInviteIn, user: CurrentUser, session: SessionDep
) -> ConnectionOut:
    email = data.email.lower()
    if email == user.email.lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="CANNOT_INVITE_SELF")
    other = session.exec(select(User).where(User.email == email)).first()
    if other is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")

    # ja existe vinculo em qualquer sentido? nao criamos um segundo
    existing = session.exec(
        select(Connection).where(
            or_(
                (Connection.requester_user_id == user.id)
                & (Connection.addressee_user_id == other.id),
                (Connection.requester_user_id == other.id)
                & (Connection.addressee_user_id == user.id),
            )
        )
    ).first()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="CONNECTION_EXISTS")

    connection = Connection(requester_user_id=user.id, addressee_user_id=other.id)
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return _connection_out(session, connection, user.id)


@router.post("/connections/{connection_id}/accept", response_model=ConnectionOut)
def accept_connection(
    connection_id: int, user: CurrentUser, session: SessionDep
) -> ConnectionOut:
    connection = _owned_connection(session, connection_id, user.id)
    # so quem RECEBEU o convite aceita: quem convidou nao aceita o proprio convite
    if connection.addressee_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="NOT_THE_INVITEE")
    if connection.status != ConnectionStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="ALREADY_ANSWERED")
    connection.status = ConnectionStatus.accepted
    connection.responded_at = datetime.now(timezone.utc)
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return _connection_out(session, connection, user.id)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_connection(connection_id: int, user: CurrentUser, session: SessionDep) -> None:
    """Recusar um convite ou desfazer uma conexao ja aceita. As copias que a pessoa
    ja aceitou continuam com ela: sao dela desde o aceite."""
    connection = _owned_connection(session, connection_id, user.id)
    other_id = _other_user_id(connection, user.id)
    # ofertas ainda pendentes entre os dois perdem o sentido e saem junto
    pending = session.exec(
        select(ShareOffer)
        .where(ShareOffer.status == ShareOfferStatus.pending)
        .where(
            or_(
                (ShareOffer.from_user_id == user.id) & (ShareOffer.to_user_id == other_id),
                (ShareOffer.from_user_id == other_id) & (ShareOffer.to_user_id == user.id),
            )
        )
    ).all()
    for offer in pending:
        session.delete(offer)
    session.delete(connection)
    session.commit()


# --- Ofertas --------------------------------------------------------------


def _accepted_partner_id(session: Session, connection_id: int, user_id: int) -> int:
    connection = _owned_connection(session, connection_id, user_id)
    if connection.status != ConnectionStatus.accepted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="NOT_CONNECTED")
    return _other_user_id(connection, user_id)


def _owned_item_name(
    session: Session, kind: SharedItemKind, item_id: int, user_id: int
) -> str:
    """Confere que o item e mesmo de quem esta oferecendo e devolve o nome para o
    snapshot da oferta."""
    if kind == SharedItemKind.recipe:
        recipe = session.get(Recipe, item_id)
        if recipe is None or recipe.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ITEM_NOT_FOUND")
        return recipe.name
    food = session.get(Food, item_id)
    # alimento do catalogo global nao e "seu" para compartilhar - a outra pessoa ja o ve
    if food is None or food.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="ITEM_NOT_FOUND")
    translation = next(iter(food.translations), None)
    return translation.name if translation is not None else food.slug


@router.post("/offers", response_model=list[ShareOfferOut], status_code=status.HTTP_201_CREATED)
def create_offers(
    data: ShareOfferIn, user: CurrentUser, session: SessionDep
) -> list[ShareOfferOut]:
    """Oferece um ou varios itens de uma vez - mandar as receitas todas no primeiro
    dia e o caso real, uma a uma seria trabalho repetitivo."""
    to_user_id = _accepted_partner_id(session, data.connection_id, user.id)
    from_name = _display_name(session, user.id)

    created: list[ShareOffer] = []
    for item in data.items:
        name = _owned_item_name(session, item.item_kind, item.item_id, user.id)
        # ja ofereceu esse item e ainda esta esperando resposta? nao duplica
        already = session.exec(
            select(ShareOffer)
            .where(ShareOffer.from_user_id == user.id)
            .where(ShareOffer.to_user_id == to_user_id)
            .where(ShareOffer.item_kind == item.item_kind)
            .where(ShareOffer.item_id == item.item_id)
            .where(ShareOffer.status == ShareOfferStatus.pending)
        ).first()
        if already is not None:
            created.append(already)
            continue
        offer = ShareOffer(
            from_user_id=user.id,
            to_user_id=to_user_id,
            item_kind=item.item_kind,
            item_id=item.item_id,
            item_name=name,
        )
        session.add(offer)
        created.append(offer)
    session.commit()
    for offer in created:
        session.refresh(offer)
    return [
        ShareOfferOut(
            id=o.id,
            item_kind=o.item_kind,
            item_name=o.item_name,
            from_name=from_name,
            created_at=o.created_at,
        )
        for o in created
    ]


@router.get("/offers", response_model=list[ShareOfferOut])
def list_offers(user: CurrentUser, session: SessionDep) -> list[ShareOfferOut]:
    """Caixa de entrada: o que esta esperando o seu aceite."""
    offers = session.exec(
        select(ShareOffer)
        .where(ShareOffer.to_user_id == user.id)
        .where(ShareOffer.status == ShareOfferStatus.pending)
        .order_by(desc(ShareOffer.created_at))
    ).all()
    return [
        ShareOfferOut(
            id=o.id,
            item_kind=o.item_kind,
            item_name=o.item_name,
            from_name=_display_name(session, o.from_user_id),
            created_at=o.created_at,
        )
        for o in offers
    ]


def _owned_offer(session: Session, offer_id: int, user_id: int) -> ShareOffer:
    offer = session.get(ShareOffer, offer_id)
    if offer is None or offer.to_user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="OFFER_NOT_FOUND")
    if offer.status != ShareOfferStatus.pending:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="ALREADY_ANSWERED")
    return offer


@router.post("/offers/{offer_id}/accept", response_model=ReceivedItemOut)
def accept_offer(offer_id: int, user: CurrentUser, session: SessionDep) -> ReceivedItemOut:
    """Copia o item para a conta de quem recebeu. Dai em diante o item e dela: pode
    editar e apagar sem afetar o original."""
    offer = _owned_offer(session, offer_id, user.id)
    try:
        if offer.item_kind == SharedItemKind.recipe:
            source = session.get(Recipe, offer.item_id)
            if source is None or source.user_id != offer.from_user_id:
                raise SourceItemGone
            copy_id = copy_recipe(session, source, user, offer.from_user_id).id
        else:
            source_food = session.get(Food, offer.item_id)
            if source_food is None or source_food.user_id != offer.from_user_id:
                raise SourceItemGone
            copy_id = copy_food(session, source_food, user, offer.from_user_id)
    except SourceItemGone:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="SOURCE_ITEM_GONE"
        ) from None

    offer.status = ShareOfferStatus.accepted
    offer.responded_at = datetime.now(timezone.utc)
    session.add(offer)
    session.commit()
    return ReceivedItemOut(
        item_kind=offer.item_kind,
        item_id=copy_id,
        from_name=_display_name(session, offer.from_user_id),
    )


@router.post("/offers/{offer_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_offer(offer_id: int, user: CurrentUser, session: SessionDep) -> None:
    offer = _owned_offer(session, offer_id, user.id)
    offer.status = ShareOfferStatus.declined
    offer.responded_at = datetime.now(timezone.utc)
    session.add(offer)
    session.commit()


@router.get("/received", response_model=list[ReceivedItemOut])
def list_received(user: CurrentUser, session: SessionDep) -> list[ReceivedItemOut]:
    """Itens que voce aceitou de alguem - alimenta a pilula "Recebidas"."""
    items = session.exec(
        select(SharedItem)
        .where(SharedItem.owner_user_id == user.id)
        .order_by(desc(SharedItem.accepted_at))
    ).all()
    names: dict[int, str] = {}
    out: list[ReceivedItemOut] = []
    for item in items:
        if item.from_user_id not in names:
            names[item.from_user_id] = _display_name(session, item.from_user_id)
        out.append(
            ReceivedItemOut(
                item_kind=item.item_kind,
                item_id=item.item_id,
                from_name=names[item.from_user_id],
            )
        )
    return out
