import datetime
from sqlalchemy import Boolean, Column, Integer, String, DateTime
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
