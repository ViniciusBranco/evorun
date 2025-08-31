from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
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
    if not db_workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    
    # Regra de autorização: verifica se o usuário logado é o dono do treino
    if db_workout.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

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
    if not db_workout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    
    # Regra de autorização: verifica se o usuário logado é o dono do treino
    if db_workout.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    crud.delete_workout(db=db, db_workout=db_workout)
    
    # Retorna uma resposta vazia com status 204, indicando sucesso na exclusão
    return Response(status_code=status.HTTP_204_NO_CONTENT)