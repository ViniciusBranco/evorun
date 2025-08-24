from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .... import crud, models, schemas
from ..deps import get_db, get_current_active_user

router = APIRouter()

@router.post("/", response_model=schemas.Workout, status_code=status.HTTP_201_CREATED)
def create_workout(
    workout: schemas.WorkoutCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Endpoint para criar um novo treino para o usuário logado.
    """
    return crud.create_user_workout(db=db, workout=workout, user_id=current_user.id)

@router.get("/", response_model=List[schemas.Workout])
def read_workouts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Endpoint para listar todos os treinos do usuário logado.
    """
    workouts = crud.get_workouts_by_user(db=db, user_id=current_user.id, skip=skip, limit=limit)
    return workouts

