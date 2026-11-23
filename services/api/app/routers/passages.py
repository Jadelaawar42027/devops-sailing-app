from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionDep
from app.models import Boat, Passage
from app.schemas import PassageIn, PassageOut

router = APIRouter(prefix="/passages", tags=["passages"])


def get_passage_or_404(session: Session, passage_id: int) -> Passage:
    passage = session.get(Passage, passage_id)
    if passage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Passage {passage_id} not found")
    return passage


def ensure_boat_exists(session: Session, boat_id: int) -> None:
    if session.get(Boat, boat_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Boat {boat_id} does not exist")


@router.get("", response_model=list[PassageOut])
def list_passages(session: SessionDep, boat_id: int | None = None):
    query = select(Passage).order_by(Passage.id)
    if boat_id is not None:
        query = query.where(Passage.boat_id == boat_id)
    return session.scalars(query).all()


@router.post("", response_model=PassageOut, status_code=status.HTTP_201_CREATED)
def create_passage(body: PassageIn, session: SessionDep):
    ensure_boat_exists(session, body.boat_id)
    passage = Passage(**body.model_dump())
    session.add(passage)
    session.commit()
    session.refresh(passage)
    return passage


@router.get("/{passage_id}", response_model=PassageOut)
def get_passage(passage_id: int, session: SessionDep):
    return get_passage_or_404(session, passage_id)


@router.put("/{passage_id}", response_model=PassageOut)
def update_passage(passage_id: int, body: PassageIn, session: SessionDep):
    passage = get_passage_or_404(session, passage_id)
    ensure_boat_exists(session, body.boat_id)
    for key, value in body.model_dump().items():
        setattr(passage, key, value)
    session.commit()
    session.refresh(passage)
    return passage


@router.delete("/{passage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_passage(passage_id: int, session: SessionDep):
    passage = get_passage_or_404(session, passage_id)
    session.delete(passage)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
