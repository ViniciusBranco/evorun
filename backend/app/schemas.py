import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


# --- Schemas de User (Base) ---
class UserBase(BaseModel):
    """
    Schema base para User, usado em outros schemas.
    """
    email: EmailStr

# --- Schemas de Workout ---
class WorkoutBase(BaseModel):
    """
    Schema base para Workout, usado em outros schemas.
    """
    distance_km: float
    duration_minutes: int
    elevation_level: Optional[int] = 0

class WorkoutCreate(WorkoutBase):
    """
    Schema para a criação de um treino.
    """
    pass

class Workout(WorkoutBase):
    """
    Schema para a leitura de um treino.
    """
    id: int
    owner_id: int
    workout_date: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

# --- Schema de User ---
class UserCreate(UserBase):
    """
    Schema para a criação de um usuário.
    """
    password: str


class User(UserBase):
    """
    Schema para a leitura de um usuário.
    """
    # Chave Primária
    id: int

    # Campos de controle
    is_active: bool
    is_superuser: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    # Campos de Perfil
    full_name: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[int] = None
    height_cm: Optional[int] = None
    training_days_per_week: Optional[int] = None

    # Relacionamento com treinos
    workouts: List[Workout] = [] 

    # Configuração para permitir que o Pydantic leia os dados
    # a partir de um modelo SQLAlchemy (ORM)
    model_config = ConfigDict(from_attributes=True)

# Schema para a atualização de um usuário (o que a API recebe para updates)
class UserUpdate(BaseModel):
    """
    Schema para a atualização de um usuário.
    Todos os campos são opcionais.
    """
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    # Adiciona os campos de perfil como opcionais
    full_name: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[int] = None
    height_cm: Optional[int] = None
    training_days_per_week: Optional[int] = None

# --- NOVOS SCHEMAS PARA TOKENS ---

class Token(BaseModel):
    """
    Schema para a resposta do token de acesso.
    """
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """
    Schema para os dados contidos dentro de um JWT.
    """
    email: Optional[str] = None

class ProfileUpdate(BaseModel):
    """
    Schema para a atualização do perfil do usuário.
    """
    full_name: str
    age: int
    weight_kg: int
    height_cm: int
    training_days_per_week: int

class WorkoutUpdate(WorkoutBase):
    distance_km: Optional[float] = None
    duration_minutes: Optional[int] = None
    elevation_level: Optional[int] = None

