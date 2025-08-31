from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    full_name = Column(String, index=True, nullable=True)
    age = Column(Integer, nullable=True)
    weight_kg = Column(Integer, nullable=True)
    height_cm = Column(Integer, nullable=True)
    training_days_per_week = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    workouts = relationship("Workout", back_populates="owner")
    
    # Adiciona a configuração para suprimir o aviso de deleção
    __mapper_args__ = {
        "confirm_deleted_rows": False,
    }

class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    distance_km = Column(Integer, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    elevation_level = Column(Integer, default=0)
    workout_date = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="workouts")

    # Adiciona a configuração para suprimir o aviso de deleção
    __mapper_args__ = {
        "confirm_deleted_rows": False,
    }
