import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

from workout_types import WorkoutType

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
    
class StairsDetails(BaseModel):
    """Schema para os detalhes específicos de um treino de escada."""
    steps: Optional[int] = None

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

    # Validador de segurança: Garante que qualquer string de workout_type
    # seja convertida para minúsculas ANTES da validação do Pydantic.
    # Isso torna a API robusta contra dados inconsistentes.
    @field_validator('workout_type', mode='before')
    @classmethod
    def lowercase_workout_type(cls, v: Any):
        if isinstance(v, str):
            return v.lower()
        return v

class WorkoutCreate(WorkoutBase):
    """
    Schema usado para criar um novo treino. Herda de WorkoutBase.
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

    # Adiciona o mesmo validador para garantir consistência na atualização.
    @field_validator('workout_type', mode='before')
    @classmethod
    def lowercase_workout_type(cls, v: Any):
        if isinstance(v, str):
            return v.lower()
        return v

class Workout(WorkoutBase):
    """
    Schema para a leitura de um treino (o que a API retorna).
    """
    id: int
    owner_id: int
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

# --- Schemas de User (sem alterações) ---

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
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
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    full_name: Optional[str] = None
    age: Optional[int] = None
    weight_kg: Optional[int] = None
    height_cm: Optional[int] = None
    training_days_per_week: Optional[int] = None

# --- Schemas de Token e Perfil (sem alterações) ---

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class ProfileUpdate(BaseModel):
    full_name: str
    age: int
    weight_kg: int
    height_cm: int
    training_days_per_week: int

