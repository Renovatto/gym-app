"""Favoritos (a estrelinha): alimentos e receitas que o usuario marcou como
preferidos. Alem de aparecerem primeiro nas listas, sao o sinal de personalizacao
mais forte do motor da nutri - mais forte que a frequencia (que e implicita)."""

from sqlmodel import Session, select

from ..models import Favorite, FavoriteKind


def favorite_food_ids(session: Session, user_id: int) -> set[int]:
    rows = session.exec(
        select(Favorite.ref_id)
        .where(Favorite.user_id == user_id)
        .where(Favorite.kind == FavoriteKind.food)
    ).all()
    return set(rows)


def favorite_recipe_ids(session: Session, user_id: int) -> set[int]:
    rows = session.exec(
        select(Favorite.ref_id)
        .where(Favorite.user_id == user_id)
        .where(Favorite.kind == FavoriteKind.recipe)
    ).all()
    return set(rows)


def toggle_favorite(session: Session, user_id: int, kind: FavoriteKind, ref_id: int) -> bool:
    """Liga/desliga o favorito. Retorna o novo estado (True = agora e favorito)."""
    existing = session.exec(
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .where(Favorite.kind == kind)
        .where(Favorite.ref_id == ref_id)
    ).first()
    if existing is not None:
        session.delete(existing)
        session.commit()
        return False
    session.add(Favorite(user_id=user_id, kind=kind, ref_id=ref_id))
    session.commit()
    return True
