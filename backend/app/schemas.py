import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict

from .workout_types import WorkoutType

# --- Schemas de Detalhes Específicos por Esporte ---

class RunningDetails(BaseModel):
    """Schema para os detalhes específicos de um treino de corrida."""
    elevation_level: Optional[int] = 0

class CyclingDetails(BaseModel):
    """Schema para os detalhes específicos de um treino de ciclismo."""
    elevation_level: Optional[int] = 0

class SwimmingDetails(BaseModel):
    """Schema para os detalhes específicos de um treino de natação."""
    pool_size_meters: Optional[int] = 50

class WeightliftingDetails(BaseModel):
    """Schema para os detalhes específicos de um treino de musculação."""
    exercise: str
    sets: int
    reps: int
    weight_kg: float

# --- Schemas de Workout Refatorados ---

class WorkoutBase(BaseModel):
    """
    Schema base para Workout, com campos comuns a todos os tipos de treino.
    """
    workout_type: WorkoutType
    workout_date: datetime.datetime
    duration_minutes: Optional[int] = None
    distance_km: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class WorkoutCreate(WorkoutBase):
    """
    Schema usado para criar um novo treino. Herda de WorkoutBase.
    A validação dos 'details' é feita no endpoint.
    """
    pass

class WorkoutUpdate(BaseModel):
    """
    Schema para a atualização de um treino. Todos os campos são opcionais.
    """
    workout_type: Optional[WorkoutType] = None
    workout_date: Optional[datetime.datetime] = None
    duration_minutes: Optional[int] = None
    distance_km: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class Workout(WorkoutBase):
    """
    Schema para a leitura de um treino (o que a API retorna).
    Inclui campos do banco de dados como 'id' e 'owner_id'.
    """
    id: int
    owner_id: int
    model_config = ConfigDict(from_attributes=True)

# --- Schemas de User ---

class UserBase(BaseModel):
    """
    Schema base para User, contendo apenas o e-mail.
    """
    email: EmailStr

class UserCreate(UserBase):
    """
    Schema para a criação de um novo usuário. Requer uma senha.
    """
    password: str

class User(UserBase):
    """
    Schema para a leitura de um usuário (o que a API retorna).
    Inclui todos os campos do perfil e a lista de treinos associados.
    """
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    full_name: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[int] = None
    height_cm: Optional[int] = None
    training_days_per_week: Optional[int] = None
    workouts: List[Workout] = [] 
    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    """
    Schema para a atualização de um usuário. Todos os campos são opcionais.
    """
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    full_name: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[int] = None
    height_cm: Optional[int] = None
    training_days_per_week: Optional[int] = None

# --- Schemas de Token e Perfil ---

class Token(BaseModel):
    """
    Schema para a resposta do token de acesso no endpoint de login.
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
    Schema usado especificamente para a atualização do perfil inicial (onboarding).
    """
    full_name: str
    age: int
    weight_kg: int
    height_cm: int
    training_days_per_week: int
