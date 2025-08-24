import datetime
from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    # Chave Primária
    id = Column(Integer, primary_key=True, index=True)

    # Campos de login obrigatórios
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # Campos de controle
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)        
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    # Campos de Perfil
    full_name = Column(String, index=True, nullable=True)
    age = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    height_cm = Column(Integer, nullable=True)
    training_days_per_week = Column(Integer, nullable=True)

    # Relacionamento com treinos: um usuário pode ter muitos treinos
    workouts = relationship("Workout", back_populates="owner")


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    distance_km = Column(Float, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    elevation_level = Column(Integer, default=0)
    workout_date = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    owner_id = Column(Integer, ForeignKey("users.id"))

    # Adiciona o relacionamento reverso: um treino pertence a um usuário
    owner = relationship("User", back_populates="workouts")