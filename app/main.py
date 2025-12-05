# app/main.py

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config.settings import settings
from app.core.database.database import init_db
from app.api.dependencies.database import get_database
from app.api.v1.endpoints import usuarios, supervisor, productos, mapa, tareas, puntos, muebles, empresas
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.security.auth import get_current_user as get_current_user_core
from app.core.database.database import get_db
from fastapi.security import OAuth2PasswordBearer
from app.core.database.init_data import init_estados_tarea
from app.api.v1.endpoints import ruta, reporte, dashboard, resumen_semanal, estadisticas
from app.api.v1.endpoints import cotizaciones, planes, facturas, actividades, backoffice
from app.api.v1.endpoints import predicciones  # Módulo ML
from app.api.v1.endpoints import auditoria  # Módulo de Auditoría


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS
origins = [
    "http://localhost:3000",  # Para React
    "http://localhost:4200",  # Para Angular
    "http://127.0.0.1:5500",  # Para VS Code Live Server
    "http://localhost:5173",  # Para Vite
    "http://127.0.0.1:5173",
    "http://localhost:8081",
    "http://localhost:8080",
    "http://localhost:8082"   # Para FastAPI en desarrollo
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Incluir los routers
app.include_router(usuarios.router)
app.include_router(supervisor.router)
app.include_router(productos.router)
app.include_router(mapa.router)
app.include_router(tareas.router)
app.include_router(puntos.router)
app.include_router(muebles.router)
app.include_router(empresas.router, prefix="/empresas", tags=["Empresas"])
app.include_router(ruta.router)
app.include_router(reporte.router)
app.include_router(dashboard.router)
app.include_router(resumen_semanal.router, prefix="/reponedor", tags=["Resumen Semanal"])
app.include_router(estadisticas.router, prefix="/admin/estadisticas", tags=["Estadísticas de Reposición"])

# Routers del módulo B2B
app.include_router(cotizaciones.router, prefix="/cotizaciones", tags=["Cotizaciones"])
app.include_router(planes.router, prefix="/planes", tags=["Planes"])
app.include_router(facturas.router, prefix="/facturas", tags=["Facturas"])
app.include_router(actividades.router, prefix="/actividades", tags=["Actividades de Cliente"])

# Router del módulo Backoffice/SuperAdmin
app.include_router(backoffice.router, prefix="/backoffice", tags=["Backoffice"])

# Router del módulo de Auditoría
app.include_router(auditoria.router, prefix="/auditoria", tags=["Auditoría"])

# Router del módulo ML/Predicciones
app.include_router(predicciones.router, prefix="/api/v1", tags=["Predicciones ML"])

# Inicializar la base de datos al arrancar la aplicación
@app.on_event("startup")
async def startup_event():
    init_db()
    init_estados_tarea()

@app.get("/")
async def root():
    return {
        "mensaje": "Bienvenido a POE - Path Optimization Engine",
        "documentacion": "/docs",
        "estado": "/health"
    }

# Ejemplo de endpoint usando la base de datos
@app.get("/health")
def health_check(db: Session = Depends(get_database)):
    try:
        # Intenta hacer una consulta simple para verificar la conexión
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/usuarios/token")

async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    user = await get_current_user_core(token=token, db=db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    return user
