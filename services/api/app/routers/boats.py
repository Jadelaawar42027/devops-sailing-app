from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionDep
from app.models import Boat, Passage
from app.schemas import BoatIn, BoatOut

router = APIRouter(prefix="/boats", tags=["boats"])


def get_boat_or_404(session: Session, boat_id: int) -> Boat:
    boat = session.get(Boat, boat_id)
    if boat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Boat {boat_id} not found")
    return boat


@router.get("", response_model=list[BoatOut])
def list_boats(session: SessionDep):
    return session.scalars(select(Boat).order_by(Boat.id)).all()


@router.post("", response_model=BoatOut, status_code=status.HTTP_201_CREATED)
def create_boat(body: BoatIn, session: SessionDep):
    boat = Boat(**body.model_dump())
    session.add(boat)
    session.commit()
    session.refresh(boat)
    return boat


@router.get("/{boat_id}", response_model=BoatOut)
def get_boat(boat_id: int, session: SessionDep):
    return get_boat_or_404(session, boat_id)


@router.put("/{boat_id}", response_model=BoatOut)
def update_boat(boat_id: int, body: BoatIn, session: SessionDep):
    boat = get_boat_or_404(session, boat_id)
    for key, value in body.model_dump().items():
        setattr(boat, key, value)
    session.commit()
    session.refresh(boat)
    return boat


@router.delete("/{boat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_boat(boat_id: int, session: SessionDep):
    boat = get_boat_or_404(session, boat_id)
    in_use = session.scalar(select(Passage.id).where(Passage.boat_id == boat_id).limit(1))
    if in_use is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Boat {boat_id} has passages; delete them first"
        )
    session.delete(boat)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
