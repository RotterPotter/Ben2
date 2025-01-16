from fastapi import APIRouter, Depends
from database import get_db
from sqlalchemy.orm import Session
from models import Barber

router = APIRouter(prefix='/barbers')

@router.get("/barbers")
async def get_barbers(
  db_session: Session = Depends(get_db)
):
  barbers = db_session.query(Barber).all()
  if len(barbers) == 0:
    db_session.add(Barber(name='Alex'))
    db_session.add(Barber(name='Luca'))
    db_session.add(Barber(name='Gioelle'))
    db_session.add(Barber(name='Chris'))
    db_session.commit()
    barbers = db_session.query(Barber).all()
  return barbers
    