from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from pydantic import ValidationError

from .... import crud, models, schemas
from ..deps import get_current_active_user, get_db
from ....workout_types import WorkoutType

router = APIRouter()

# Mapeia o tipo de treino para o schema de detalhes correspondente
DETAILS_SCHEMA_MAP = {
    WorkoutType.RUNNING: schemas.RunningDetails,
    WorkoutType.CYCLING: schemas.CyclingDetails,
    WorkoutType.SWIMMING: schemas.SwimmingDetails,
    WorkoutType.WEIGHTLIFTING: schemas.WeightliftingDetails,
}

@router.post("/", response_model=schemas.Workout, status_code=status.HTTP_201_CREATED)
def create_workout(
    workout_in: schemas.WorkoutCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Endpoint para criar um novo treino.
    Valida os 'details' com base no 'workout_type'.
    """
    details_schema = DETAILS_SCHEMA_MAP.get(workout_in.workout_type)
    if not details_schema:
        raise HTTPException(status_code=400, detail="Tipo de treino inválido.")
    
    try:
        # Valida o dicionário de detalhes com o schema Pydantic correto
        validated_details = details_schema.model_validate(workout_in.details or {})
        workout_in.details = validated_details.model_dump()
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    return crud.create_user_workout(db=db, workout=workout_in, user_id=current_user.id)

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
    workouts = crud.get_workouts_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return workouts

@router.put("/{workout_id}", response_model=schemas.Workout)
def update_workout(
    workout_id: int,
    workout_in: schemas.WorkoutUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Endpoint para atualizar um treino existente.
    """
    db_workout = crud.get_workout(db, workout_id=workout_id)
    if not db_workout or db_workout.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")

    if workout_in.details is not None:
        workout_type_to_check = workout_in.workout_type or db_workout.workout_type
        details_schema = DETAILS_SCHEMA_MAP.get(workout_type_to_check)
        if not details_schema:
            raise HTTPException(status_code=400, detail="Tipo de treino inválido.")
        try:
            validated_details = details_schema.model_validate(workout_in.details)
            workout_in.details = validated_details.model_dump()
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())

    updated_workout = crud.update_workout(db=db, db_workout=db_workout, workout_in=workout_in)
    return updated_workout

@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(
    workout_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Endpoint para excluir um treino existente.
    """
    db_workout = crud.get_workout(db, workout_id=workout_id)
    if not db_workout or db_workout.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    
    crud.delete_workout(db=db, db_workout=db_workout)
    return Response(status_code=status.HTTP_204_NO_CONTENT)