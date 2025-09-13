from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import crud, models, schemas
from api.v1.deps import get_db, get_current_active_user


router = APIRouter()

# --- Endpoints ---

# A criação de usuário continua pública, pois qualquer um pode se registrar
@router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Endpoint para criar um novo usuário.
    - user: Corpo da requisição, validado pelo schema UserCreate.
    - db: Sessão do banco de dados injetada pela dependência get_db.
    """
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

# Endpoint protegido: Apenas usuários logados podem listar outros usuários.
@router.get("/", response_model=List[schemas.User])
def read_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Endpoint para listar usuários com paginação.
    """
    # Regra de autorização: Apenas superusuários podem listar todos os usuários.
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to list all users"
        )
    users = crud.get_users(db, skip=skip, limit=limit)
    return users


# Endpoint protegido com autorização: Usuário só pode ver a si mesmo.
@router.get("/{user_id}", response_model=schemas.User)
def read_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user) # 2. Protege a rota
):
    """
    Endpoint para buscar um usuário pelo seu ID.
    """
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# Endpoint protegido com autorização: Usuário só pode atualizar a si mesmo.
@router.put("/{user_id}", response_model=schemas.User)
def update_user(
    user_id: int, 
    user_in: schemas.UserUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user) # 2. Protege a rota
):
    """
    Endpoint para atualizar um usuário.
    """
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Um usuário normal não pode se tornar superusuário
    if user_in.is_superuser and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign superuser role")

    if user_in.email:
        existing_user = crud.get_user_by_email(db, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=400, detail="Email already in use")
            
    updated_user = crud.update_user(db=db, db_user=db_user, user_in=user_in)
    return updated_user

# Endpoint protegido com autorização: Usuário só pode deletar a si mesmo.
@router.delete("/{user_id}", response_model=schemas.User)
def delete_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user) # 2. Protege a rota
):
    """
    Endpoint para deletar um usuário.
    """
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    crud.delete_user(db=db, user_id=user_id)
    return db_user

@router.get("/me/", response_model=schemas.User)
def read_user_me(current_user: models.User = Depends(get_current_active_user)):
    """
    Endpoint para obter os dados do usuário logado.
    """
    return current_user

@router.put("/me/profile", response_model=schemas.User)
def update_user_profile(
    profile_in: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Endpoint para o usuário preencher/atualizar seu perfil inicial.
    """
    # Converte o schema para um dicionário para usar na função de update
    user_in = schemas.UserUpdate(**profile_in.model_dump())
    updated_user = crud.update_user(db=db, db_user=current_user, user_in=user_in)
    return updated_user