"""Novidades do app, do lado de quem usa: listar, contar nao lidas e marcar como lida.

O que o admin escreve fica em routers/admin.py; aqui so entra leitura. Ver
services/news.py para o criterio editorial e para a decisao de guardar o texto no banco.
"""

from fastapi import APIRouter, status
from sqlmodel import select

from ..deps import CurrentUser, SessionDep
from ..models import NewsImportance, NewsItem, NewsRead
from ..schemas import NewsFeed, NewsItemOut
from ..services.news import localized_news

router = APIRouter(prefix="/me/news", tags=["news"])


def _to_out(item: NewsItem, locale: str, read: bool) -> NewsItemOut:
    title, body = localized_news(item, locale)
    return NewsItemOut(
        id=item.id,
        published_on=item.published_on,
        importance=item.importance,
        title=title,
        body=body,
        read=read,
    )


@router.get("", response_model=NewsFeed)
def list_news(user: CurrentUser, session: SessionDep) -> NewsFeed:
    items = session.exec(
        select(NewsItem)
        .where(NewsItem.published.is_(True))
        .order_by(NewsItem.published_on.desc(), NewsItem.id.desc())
    ).all()

    read_ids = set(
        session.exec(select(NewsRead.news_id).where(NewsRead.user_id == user.id)).all()
    )

    out = [_to_out(item, user.locale, item.id in read_ids) for item in items]

    # A modal so interrompe pela novidade importante mais recente ainda nao lida. Se
    # houver duas, as outras ficam na lista - abrir tres modais seguidas ensinaria o
    # usuario a fechar sem ler, que e justamente o que a distincao de importancia evita.
    pending = next(
        (
            entry
            for entry, item in zip(out, items)
            if not entry.read and item.importance == NewsImportance.important
        ),
        None,
    )

    return NewsFeed(
        items=out,
        unread_count=sum(1 for entry in out if not entry.read),
        pending_important=pending,
    )


@router.post("/{news_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(news_id: int, user: CurrentUser, session: SessionDep) -> None:
    """Marca uma novidade como lida. Idempotente de proposito: a tela chama isso para
    cada item visivel ao abrir, e a modal chama de novo ao fechar."""
    ja_lida = session.get(NewsRead, (user.id, news_id))
    if ja_lida is not None:
        return
    # Novidade despublicada ou inexistente nao vira leitura: evita linha orfa apontando
    # para id que o admin apagou.
    item = session.get(NewsItem, news_id)
    if item is None or not item.published:
        return
    session.add(NewsRead(user_id=user.id, news_id=news_id))
    session.commit()
