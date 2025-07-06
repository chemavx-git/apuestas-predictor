from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

# Carga variables de entorno (GitHub Actions inyecta las vars, dotenv solo para local)
load_dotenv()

# Construye la URL de conexión a PostgreSQL
DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)

# Motor y sesión de SQLAlchemy
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Team(Base):
    __tablename__ = "teams"

    id   = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    # Partidos como local
    home_matches = relationship(
        "Match",
        foreign_keys="[Match.home_team_id]",
        back_populates="home_team",
        cascade="all, delete-orphan",
    )
    # Partidos como visitante
    away_matches = relationship(
        "Match",
        foreign_keys="[Match.away_team_id]",
        back_populates="away_team",
        cascade="all, delete-orphan",
    )


class Match(Base):
    __tablename__ = "matches"

    id            = Column(Integer, primary_key=True)
    external_id   = Column(Integer, nullable=False, unique=True)
    utc_date      = Column(DateTime, nullable=False)
    home_team_id  = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id  = Column(Integer, ForeignKey("teams.id"), nullable=False)
    competition   = Column(String, nullable=False)

    # Relaciones inversas hacia Team
    home_team = relationship(
        "Team",
        foreign_keys=[home_team_id],
        back_populates="home_matches"
    )
    away_team = relationship(
        "Team",
        foreign_keys=[away_team_id],
        back_populates="away_matches"
    )

    __table_args__ = (
        UniqueConstraint("external_id", name="uq_match_external"),
    )


class Odds(Base):
    __tablename__ = "odds"

    id           = Column(Integer, primary_key=True)
    match_id     = Column(Integer, ForeignKey("matches.id"), nullable=False)
    provider     = Column(String, nullable=False)
    market       = Column(String, nullable=False)
    decimal_odds = Column(Float, nullable=False)
    fetched_at   = Column(DateTime, nullable=False)

    match = relationship("Match")


# Punto de entrada para crear tablas manualmente si se ejecuta el módulo
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
