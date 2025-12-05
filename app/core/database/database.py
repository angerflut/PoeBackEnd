from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import Engine
from typing import Generator
from app.core.config.settings import settings

class Database:
    def __init__(self):
        self.engine: Engine = self._create_engine()
        self.SessionLocal = self._create_session()
        self.Base = declarative_base()

    def _create_engine(self) -> Engine:
        return create_engine(
            settings.DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            echo=False  # Desactivado para reducir logs
        )

    def _create_session(self) -> sessionmaker:
        return sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_db(self) -> Generator:
        """
        Dependencia para obtener una sesión de base de datos.
        Se usa con FastAPI para la inyección de dependencias.
        """
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def init_db(self) -> None:
        """
        Inicializa la base de datos creando todas las tablas.
        """
        try:
            self.Base.metadata.create_all(bind=self.engine)
        except Exception as e:
            print(f"Error al inicializar la base de datos: {e}")
            raise

# Instancia global de la base de datos
db = Database()
Base = db.Base
get_db = db.get_db
init_db = db.init_db
