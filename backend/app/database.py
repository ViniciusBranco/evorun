from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL de conexão com o banco de dados PostgreSQL.
# No futuro, isso virá de variáveis de ambiente.
SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/evorun"

# Cria o "motor" de conexão com o banco de dados
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Cria uma fábrica de sessões que serão as conexões individuais com o banco
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Uma classe base da qual todos os nossos modelos de banco de dados irão herdar
Base = declarative_base()
