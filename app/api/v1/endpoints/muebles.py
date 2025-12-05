from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from app.core.database.database import get_db
from app.models.mueble_reposicion import MuebleReposicion
from app.models.objeto_mapa import ObjetoMapa
from app.models.objeto_tipo import ObjetoTipo
from app.models.ubicacion_fisica import UbicacionFisica
from app.models.mapa import Mapa
from app.models.punto_reposicion import PuntoReposicion
from app.core.security.auth import get_current_user
from app.models.usuario import Usuario
from app.repositories import punto_reposicion as punto_reposicion_repository
from app.schemas.mueble_reposicion import MuebleCompletoCreate

router = APIRouter()

@router.get("/muebles/reposicion")
def listar_muebles_reposicion(db: Session = Depends(get_db)):
    muebles = db.query(MuebleReposicion).all()
    resultado = []
    for mueble in muebles:
        objeto = db.query(ObjetoMapa).filter(ObjetoMapa.id_objeto == mueble.id_objeto).first()
        if not objeto:
            continue
        tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == objeto.id_tipo).first()
        ubicaciones = db.query(UbicacionFisica).filter(UbicacionFisica.id_objeto == objeto.id_objeto).all()
        ubicaciones_list = []
        for ubic in ubicaciones:
            mapa = db.query(Mapa).filter(Mapa.id_mapa == ubic.id_mapa).first()
            ubicaciones_list.append({
                "x": ubic.x,
                "y": ubic.y,
                "mapa": {
                    "id_mapa": mapa.id_mapa if mapa else None,
                    "nombre": mapa.nombre if mapa else None,
                    "ancho": mapa.ancho if mapa else None,
                    "alto": mapa.alto if mapa else None
                }
            })
        resultado.append({
            "id_mueble": mueble.id_mueble,
            "filas": mueble.filas,
            "columnas": mueble.columnas,
            "objeto_mapa": {
                "id_objeto": objeto.id_objeto,
                "nombre": objeto.nombre,
                "tipo": {
                    "id_tipo": tipo.id_tipo if tipo else None,
                    "nombre_tipo": tipo.nombre_tipo if tipo else None,
                    "caminable": tipo.caminable if tipo else None,
                    "destino": tipo.destino if tipo else None
                },
                "ubicaciones": ubicaciones_list
            }
        })
    return resultado

@router.post("/muebles/reposicion", status_code=201)
def crear_mueble_reposicion(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    id_objeto = body.get("id_objeto")
    filas = body.get("filas")
    columnas = body.get("columnas")
    direccion = (body.get("direccion") or "T").upper()
    if not id_objeto or not isinstance(filas, int) or not isinstance(columnas, int) or filas <= 0 or columnas <= 0:
        raise HTTPException(status_code=422, detail="id_objeto, filas y columnas son requeridos y deben ser mayores a cero.")
    # Validar direccion
    if direccion not in ["N", "S", "E", "O", "T"]:
        raise HTTPException(status_code=422, detail="direccion debe ser una de: N,S,E,O,T")
    try:
        # Crear mueble y generar puntos usando repositorio (evita lógica duplicada)
        mueble = MuebleReposicion(
            id_objeto=id_objeto,
            filas=filas,
            columnas=columnas,
            direccion=direccion,
            id_empresa=current_user.id_empresa
        )
        db.add(mueble)
        db.flush()  # obtener id_mueble

        # Generar puntos en bloque
        punto_reposicion_repository.generar_puntos_mueble(
            db,
            mueble.id_mueble,
            filas,
            columnas,
            current_user.id_empresa
        )

        db.commit()
        db.refresh(mueble)

        # Consultar puntos generados para la respuesta
        puntos = db.query(PuntoReposicion).filter(PuntoReposicion.id_mueble == mueble.id_mueble).all()
        return {
            "mueble": {
                "id_mueble": mueble.id_mueble,
                "id_objeto": mueble.id_objeto,
                "filas": mueble.filas,
                "columnas": mueble.columnas
            },
            "puntos": [
                {"id_punto": p.id_punto, "nivel": p.nivel, "estanteria": p.estanteria} for p in puntos
            ]
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear mueble o puntos: {str(e)}")

@router.post("/muebles/completo", status_code=201)
def crear_mueble_completo(
    mueble_in: MuebleCompletoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Crea un Mueble desde cero:
    1. Crea el ObjetoMapa (entidad mueble)
    2. Crea la configuración MuebleReposicion
    3. Genera los puntos de reposición automáticamente
    """
    try:
        direccion = (mueble_in.direccion or "T").upper()
        if direccion not in ["N","S","E","O","T"]:
            raise HTTPException(status_code=422, detail="direccion debe ser una de: N,S,E,O,T")

        # Buscar id del tipo 'mueble' por nombre; si no existe, usar 3
        tipo_mueble = db.query(ObjetoTipo).filter(ObjetoTipo.nombre_tipo.ilike("mueble")).first()
        id_tipo_mueble = tipo_mueble.id_tipo if tipo_mueble else 3

        # Crear objeto
        nuevo_objeto = ObjetoMapa(
            nombre=mueble_in.nombre,
            id_tipo=id_tipo_mueble,
            id_empresa=current_user.id_empresa
        )
        db.add(nuevo_objeto)
        db.flush()

        # Crear mueble reposición
        nuevo_mueble = MuebleReposicion(
            id_objeto=nuevo_objeto.id_objeto,
            filas=mueble_in.filas,
            columnas=mueble_in.columnas,
            direccion=direccion,
            id_empresa=current_user.id_empresa
        )
        db.add(nuevo_mueble)
        db.flush()

        # Generar puntos
        punto_reposicion_repository.generar_puntos_mueble(
            db,
            nuevo_mueble.id_mueble,
            nuevo_mueble.filas,
            nuevo_mueble.columnas,
            current_user.id_empresa
        )

        db.commit()
        db.refresh(nuevo_objeto)
        db.refresh(nuevo_mueble)
        
        # Consultar puntos generados para confirmar
        puntos = db.query(PuntoReposicion).filter(PuntoReposicion.id_mueble == nuevo_mueble.id_mueble).all()
        
        return {
            "mensaje": "Mueble creado exitosamente",
            "id_objeto": nuevo_objeto.id_objeto,
            "id_mueble": nuevo_mueble.id_mueble,
            "nombre": nuevo_objeto.nombre,
            "filas": nuevo_mueble.filas,
            "columnas": nuevo_mueble.columnas,
            "capacidad": f"{nuevo_mueble.filas}x{nuevo_mueble.columnas}",
            "puntos_generados": len(puntos),
            "puntos": [
                {"id_punto": p.id_punto, "nivel": p.nivel, "estanteria": p.estanteria} for p in puntos
            ]
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear mueble: {str(e)}")

@router.get("/muebles/{id_objeto}/info")
def obtener_info_mueble(
    id_objeto: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene información completa de un mueble incluyendo sus puntos de reposición.
    Útil para verificar el estado de un mueble antes de asignar productos.
    """
    try:
        # Verificar que el objeto existe y es de la empresa del usuario
        objeto = db.query(ObjetoMapa).filter(
            ObjetoMapa.id_objeto == id_objeto,
            ObjetoMapa.id_empresa == current_user.id_empresa
        ).first()
        
        if not objeto:
            raise HTTPException(status_code=404, detail="Objeto no encontrado")
        
        # Verificar que es un mueble
        tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == objeto.id_tipo).first()
        if not tipo or tipo.nombre_tipo.lower() != 'mueble':
            raise HTTPException(status_code=422, detail="El objeto no es un mueble")
        
        # Buscar el mueble de reposición
        mueble = db.query(MuebleReposicion).filter(
            MuebleReposicion.id_objeto == id_objeto
        ).first()
        
        if not mueble:
            return {
                "id_objeto": id_objeto,
                "nombre": objeto.nombre,
                "tiene_configuracion": False,
                "mensaje": "Este mueble no tiene configuración de reposición. Use POST /muebles/reposicion para configurarlo."
            }
        
        # Contar puntos existentes
        puntos = db.query(PuntoReposicion).filter(
            PuntoReposicion.id_mueble == mueble.id_mueble
        ).all()
        
        puntos_con_producto = [p for p in puntos if p.id_producto is not None]
        
        return {
            "id_objeto": id_objeto,
            "id_mueble": mueble.id_mueble,
            "nombre": objeto.nombre,
            "tiene_configuracion": True,
            "filas": mueble.filas,
            "columnas": mueble.columnas,
            "capacidad_total": mueble.filas * mueble.columnas,
            "puntos_generados": len(puntos),
            "puntos_con_producto": len(puntos_con_producto),
            "puntos_vacios": len(puntos) - len(puntos_con_producto),
            "tiene_puntos": len(puntos) > 0
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener información del mueble: {str(e)}")

@router.post("/muebles/{id_objeto}/validar-y-regenerar-puntos", status_code=200)
def validar_y_regenerar_puntos(
    id_objeto: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Valida que un mueble tenga puntos de reposición y los regenera si no existen.
    Este endpoint es útil para arreglar muebles creados antes de implementar la generación automática.
    """
    try:
        # Verificar que el objeto existe y es de la empresa del usuario
        objeto = db.query(ObjetoMapa).filter(
            ObjetoMapa.id_objeto == id_objeto,
            ObjetoMapa.id_empresa == current_user.id_empresa
        ).first()
        
        if not objeto:
            raise HTTPException(status_code=404, detail="Objeto no encontrado")
        
        # Verificar que es un mueble
        tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == objeto.id_tipo).first()
        if not tipo or tipo.nombre_tipo.lower() != 'mueble':
            raise HTTPException(status_code=422, detail="El objeto no es un mueble")
        
        # Buscar el mueble de reposición
        mueble = db.query(MuebleReposicion).filter(
            MuebleReposicion.id_objeto == id_objeto
        ).first()
        
        if not mueble:
            raise HTTPException(
                status_code=404, 
                detail="Este mueble no tiene configuración de reposición. Debe ser creado usando el endpoint /muebles/completo"
            )
        
        # Contar puntos existentes
        puntos_existentes = db.query(PuntoReposicion).filter(
            PuntoReposicion.id_mueble == mueble.id_mueble
        ).count()
        
        if puntos_existentes > 0:
            return {
                "mensaje": "El mueble ya tiene puntos de reposición",
                "accion": "ninguna",
                "puntos_existentes": puntos_existentes,
                "capacidad": f"{mueble.filas}x{mueble.columnas}"
            }
        
        # Generar puntos
        punto_reposicion_repository.generar_puntos_mueble(
            db,
            mueble.id_mueble,
            mueble.filas,
            mueble.columnas,
            current_user.id_empresa
        )
        
        db.commit()
        
        puntos_generados = mueble.filas * mueble.columnas
        
        return {
            "mensaje": "Puntos de reposición generados exitosamente",
            "accion": "regenerados",
            "puntos_generados": puntos_generados,
            "nombre": objeto.nombre,
            "capacidad": f"{mueble.filas}x{mueble.columnas}"
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al validar/regenerar puntos: {str(e)}")
