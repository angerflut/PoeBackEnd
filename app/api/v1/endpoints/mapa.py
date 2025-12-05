from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from app.core.database.database import get_db
from app.api.dependencies.auth import get_current_user
from app.models.usuario import Usuario, RolEnum
from app.models.mapa import Mapa
from app.models.supervision import Supervision
from app.models.ubicacion_fisica import UbicacionFisica
from app.models.objeto_mapa import ObjetoMapa
from app.models.objeto_tipo import ObjetoTipo
from app.models.mueble_reposicion import MuebleReposicion
from app.models.punto_reposicion import PuntoReposicion
from app.models.producto import Producto
from app.schemas.mapa import (
    MapeoReposicionResponse,
    MapaOut,
    UbicacionOut,
    ObjetoOut,
    MuebleOut,
    PuntoReposicionOut,
    ProductoAsociado,
    ObjetoListadoOut,
    ObjetoTipoListadoOut,
    LayoutCompletoCreate,
)
from app.schemas.mapa_vista import (
    MapaVistaGraficaResponse, MapaVistaOut, ObjetoUbicacionOut, ObjetoMapaVistaOut, ObjetoTipoOut, MuebleVistaOut, PuntoReposicionVistaOut
)
from sqlalchemy.exc import SQLAlchemyError
from app.repositories.punto_reposicion import desasignar_producto_de_punto
from app.repositories import punto_reposicion as punto_reposicion_repository
from typing import List

router = APIRouter()

# Schemas movidos a app/schemas/mapa.py (ObjetoTipoListadoOut, ObjetoListadoOut)

# Listar todos los mapas de mi empresa
@router.get("/todos", response_model=List[MapaOut])
def listar_mis_mapas(
    incluir_inactivos: bool = Query(True, description="Si es True, incluye mapas activos e inactivos. Si es False, solo activos."),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Lista los mapas de la empresa del usuario. Por defecto incluye todos (activos e inactivos)."""
    query = db.query(Mapa).filter(Mapa.id_empresa == current_user.id_empresa)

    if not incluir_inactivos:
        query = query.filter(Mapa.activo == True)

    mapas = query.all()
    return [MapaOut(id=m.id_mapa, nombre=m.nombre, ancho=m.ancho, alto=m.alto, activo=m.activo) for m in mapas]

# Activar un mapa propio y desactivar los demás
@router.put("/{id_mapa}/activar", response_model=MapaOut)
def activar_mapa(
    id_mapa: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Activa un mapa y desactiva todos los demás de la empresa.
    """
    mapa_a_activar = db.query(Mapa).filter(
        Mapa.id_mapa == id_mapa,
        Mapa.id_empresa == current_user.id_empresa
    ).first()

    if not mapa_a_activar:
        raise HTTPException(status_code=404, detail="Mapa no encontrado.")

    try:
        # Desactivar TODOS los mapas de esta empresa
        db.query(Mapa).filter(Mapa.id_empresa == current_user.id_empresa).update({"activo": False})
        # Activar el seleccionado
        mapa_a_activar.activo = True
        db.commit()
        db.refresh(mapa_a_activar)
        return MapaOut(id=mapa_a_activar.id_mapa, nombre=mapa_a_activar.nombre, ancho=mapa_a_activar.ancho, alto=mapa_a_activar.alto)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al cambiar mapa activo: {str(e)}")

@router.get("/mapa/reposicion", response_model=MapeoReposicionResponse)
def visualizar_mapa_reposicion(
    id_mapa: int = Query(None, description="ID del mapa a consultar (opcional)"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if not current_user or current_user.rol.nombre_rol != RolEnum.ADMINISTRADOR.value:
        raise HTTPException(status_code=403, detail="Solo administradores pueden consultar el mapeado de reposición.")
    # Seleccionar el mapa
    # Selección de mapa filtrando SIEMPRE por empresa del usuario
    if id_mapa is None:
        mapa = db.query(Mapa).filter(
            Mapa.id_empresa == current_user.id_empresa,
            Mapa.activo == True
        ).first()
    else:
        mapa = db.query(Mapa).filter(
            Mapa.id_mapa == id_mapa,
            Mapa.id_empresa == current_user.id_empresa,
            Mapa.activo == True
        ).first()
    if not mapa:
        return {"mensaje": "No hay mapas registrados.", "mapa": None, "ubicaciones": []}
    ubicaciones_db = db.query(UbicacionFisica).filter(UbicacionFisica.id_mapa == mapa.id_mapa).all()
    if not ubicaciones_db:
        return {"mensaje": "No hay ubicaciones cargadas.", "mapa": MapaOut(id=mapa.id_mapa, nombre=mapa.nombre, ancho=mapa.ancho, alto=mapa.alto), "ubicaciones": []}
    ubicaciones = []
    for ubic in ubicaciones_db:
        objeto = db.query(ObjetoMapa).filter(ObjetoMapa.id_objeto == ubic.id_objeto).first() if ubic.id_objeto else None
        objeto_out = None
        mueble_out = None
        if objeto:
            tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == objeto.id_tipo).first()
            objeto_out = ObjetoOut(
                nombre=objeto.nombre,
                tipo=tipo.nombre_tipo if tipo else "",
                caminable=tipo.caminable if tipo else None
            )
            # Buscar configuración de mueble si existe
            mueble = db.query(MuebleReposicion).filter(MuebleReposicion.id_objeto == objeto.id_objeto).first()
            if mueble:
                # Obtener puntos de reposición del mueble
                puntos_db = db.query(PuntoReposicion).filter(PuntoReposicion.id_mueble == mueble.id_mueble).all()
                puntos_out = []
                for punto in puntos_db:
                    producto = db.query(Producto).filter(Producto.id_producto == punto.id_producto).first() if punto.id_producto else None
                    producto_out = None
                    if producto:
                        producto_out = ProductoAsociado(
                            nombre=producto.nombre,
                            categoria=producto.categoria,
                            unidad_tipo=producto.unidad_tipo,
                            unidad_cantidad=producto.unidad_cantidad
                        )
                    puntos_out.append(PuntoReposicionOut(
                        id_punto=punto.id_punto,
                        id_mueble=punto.id_mueble,
                        nivel=punto.nivel,
                        estanteria=punto.estanteria,
                        producto=producto_out
                    ))
                # Crear objeto mueble con los puntos (puede estar vacío si no hay puntos)
                mueble_out = MuebleOut(
                    filas=mueble.filas,
                    columnas=mueble.columnas,
                    puntos_reposicion=puntos_out
                )
        ubicaciones.append(UbicacionOut(
            x=ubic.x,
            y=ubic.y,
            objeto=objeto_out,
            mueble=mueble_out
        ))
    # Devolver el mapa con todas las ubicaciones, incluso si algunos muebles no tienen puntos
    return {
        "mapa": MapaOut(id=mapa.id_mapa, nombre=mapa.nombre, ancho=mapa.ancho, alto=mapa.alto),
        "ubicaciones": ubicaciones
    }

@router.get("/mapa/vista-grafica", response_model=MapaVistaGraficaResponse)
def vista_grafica_mapa(
    id_mapa: int = Query(None, description="ID del mapa a consultar (opcional)"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if not current_user or current_user.rol.nombre_rol != RolEnum.ADMINISTRADOR.value:
        raise HTTPException(status_code=403, detail="Solo administradores pueden consultar la vista gráfica del mapa.")
    # Selección de mapa filtrando SIEMPRE por empresa del usuario
    if id_mapa is None:
        mapa = db.query(Mapa).filter(
            Mapa.id_empresa == current_user.id_empresa,
            Mapa.activo == True
        ).first()
    else:
        mapa = db.query(Mapa).filter(
            Mapa.id_mapa == id_mapa,
            Mapa.id_empresa == current_user.id_empresa
        ).first()
    if not mapa:
        return {"mensaje": "No hay mapas registrados.", "mapa": None, "objetos": []}
    ubicaciones_db = db.query(UbicacionFisica).filter(UbicacionFisica.id_mapa == mapa.id_mapa).all()
    if not ubicaciones_db:
        return {"mensaje": "No hay ubicaciones cargadas.", "mapa": MapaVistaOut(id=mapa.id_mapa, nombre=mapa.nombre, ancho=mapa.ancho, alto=mapa.alto), "objetos": []}
    objetos = []
    for ubic in ubicaciones_db:
        # Validación de límites espaciales
        if ubic.x > mapa.ancho or ubic.y > mapa.alto:
            raise HTTPException(status_code=422, detail=f"Coordenadas fuera del límite del mapa: ({ubic.x}, {ubic.y})")
        objeto = db.query(ObjetoMapa).filter(ObjetoMapa.id_objeto == ubic.id_objeto).first() if ubic.id_objeto else None
        if not objeto:
            continue
        tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == objeto.id_tipo).first()
        tipo_out = ObjetoTipoOut(
            nombre_tipo=tipo.nombre_tipo if tipo else "",
            caminable=tipo.caminable if tipo else None,
            destino=tipo.destino if tipo else None
        )
        objeto_out = ObjetoMapaVistaOut(
            id=objeto.id_objeto,
            nombre=objeto.nombre,
            tipo=tipo_out
        )
        mueble = db.query(MuebleReposicion).filter(MuebleReposicion.id_objeto == objeto.id_objeto).first()
        mueble_out = None
        if mueble:
            puntos_db = db.query(PuntoReposicion).filter(PuntoReposicion.id_mueble == mueble.id_mueble).all()
            puntos_out = []
            for punto in puntos_db:
                # Validación de límites internos del mueble
                if punto.nivel > mueble.filas or punto.estanteria > mueble.columnas:
                    raise HTTPException(status_code=422, detail=f"El punto de reposición (id {punto.id_punto}) excede la capacidad del mueble.")
                puntos_out.append(PuntoReposicionVistaOut(
                    id_punto=punto.id_punto,
                    nivel=punto.nivel,
                    estanteria=punto.estanteria
                ))
            mueble_out = MuebleVistaOut(
                filas=mueble.filas,
                columnas=mueble.columnas,
                puntos_reposicion=puntos_out
            )
        objetos.append(ObjetoUbicacionOut(
            x=ubic.x,
            y=ubic.y,
            objeto=objeto_out,
            mueble=mueble_out
        ))
    return {
        "mapa": MapaVistaOut(id=mapa.id_mapa, nombre=mapa.nombre, ancho=mapa.ancho, alto=mapa.alto),
        "objetos": objetos
    }

@router.get("/mapa/supervisor")
def vista_puntos_supervisor(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if current_user.rol.nombre_rol.lower() != "supervisor":
        raise HTTPException(status_code=403, detail="Solo los supervisores pueden acceder a este recurso.")


    # Obtener puntos asignados por usuario_punto
    puntos_usuario = db.query(PuntoReposicion.id_punto).filter(PuntoReposicion.id_usuario == current_user.id_usuario).all()
    puntos_usuario_ids = [p[0] for p in puntos_usuario]

    # Obtener reponedores supervisados por este supervisor
    reponedores = db.query(Supervision.reponedor_id).filter(Supervision.supervisor_id == current_user.id_usuario).all()
    reponedor_ids = [r[0] for r in reponedores]

    # Obtener puntos asignados a los reponedores supervisados
    puntos_reponedores = []
    if reponedor_ids:
        puntos_reponedores = db.query(PuntoReposicion.id_punto).filter(PuntoReposicion.id_usuario.in_(reponedor_ids)).all()
    puntos_reponedores_ids = [p[0] for p in puntos_reponedores]

    # Unir todos los puntos asignados
    puntos_ids_asignados = set(puntos_usuario_ids + puntos_reponedores_ids)

    # Obtener todos los puntos del mapa del supervisor
    # Primero, obtener un punto asignado
    primer_punto = db.query(PuntoReposicion).filter(PuntoReposicion.id_punto.in_(list(puntos_ids_asignados))).first()
    if not primer_punto:
        return {"mensaje": "No tienes puntos de reposición asignados actualmente."}
    # Validar empresa en toda la cadena
    mueble = db.query(MuebleReposicion).filter(MuebleReposicion.id_mueble == primer_punto.id_mueble).first()
    if not mueble:
        return {"mensaje": "No se encontró el mueble asociado a tus puntos."}
    objeto = db.query(ObjetoMapa).filter(ObjetoMapa.id_objeto == mueble.id_objeto).first()
    if not objeto:
        return {"mensaje": "No se encontró el objeto asociado al mueble."}
    ubicacion = db.query(UbicacionFisica).filter(UbicacionFisica.id_objeto == objeto.id_objeto).first()
    if not ubicacion:
        return {"mensaje": "No se encontró la ubicación asociada al objeto."}
    mapa = db.query(Mapa).filter(
        Mapa.id_mapa == ubicacion.id_mapa,
        Mapa.id_empresa == current_user.id_empresa,
        Mapa.activo == True
    ).first()
    if not mapa:
        return {"mensaje": "No se encontró el mapa asociado a tus puntos en tu empresa."}

    # Obtener todos los puntos del mapa
    muebles = db.query(MuebleReposicion).all()
    puntos_todos = db.query(PuntoReposicion).all()
    ubicaciones = db.query(UbicacionFisica).filter(UbicacionFisica.id_mapa == mapa.id_mapa).all()
    objetos = {o.id_objeto: o for o in db.query(ObjetoMapa).all()}

    respuesta = {
        "mapa": {
            "id": mapa.id_mapa,
            "nombre": mapa.nombre,
            "ancho": mapa.ancho,
            "alto": mapa.alto
        },
        "puntos": []
    }

    for punto in puntos_todos:
        # Buscar la ubicación y objeto relacionados
        mueble = next((m for m in muebles if m.id_mueble == punto.id_mueble), None)
        if not mueble:
            continue
        objeto = objetos.get(mueble.id_objeto)
        if not objeto:
            continue
        ubicacion = next((u for u in ubicaciones if u.id_objeto == objeto.id_objeto), None)
        if not ubicacion:
            continue
        producto = db.query(Producto).filter(Producto.id_producto == punto.id_producto).first() if punto.id_producto else None
        respuesta["puntos"].append({
            "x": ubicacion.x,
            "y": ubicacion.y,
            "punto_id": punto.id_punto,
            "pasillo": objeto.nombre,
            "estanteria": punto.estanteria,
            "nivel": punto.nivel,
            "detalle": producto.nombre if producto else None,
            "resaltado": punto.id_punto in puntos_ids_asignados
        })

    return respuesta

@router.post("/puntos/asignar")
def asignar_punto_usuario(
    id_usuario: int = Body(..., embed=True),
    id_punto: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if current_user.rol.nombre_rol.lower() not in ["administrador", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para asignar puntos.")
    usuario = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    punto = db.query(PuntoReposicion).filter(PuntoReposicion.id_punto == id_punto).first()
    if not usuario or not punto:
        raise HTTPException(status_code=404, detail="Usuario o punto no encontrado.")
    punto.id_usuario = id_usuario
    db.commit()
    db.refresh(punto)
    return {"mensaje": "Punto asignado correctamente", "id_punto": id_punto, "id_usuario": id_usuario}

@router.delete("/puntos/desasignar")
def desasignar_punto_usuario(
    id_punto: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    # Solo administradores o supervisores pueden desasignar puntos
    if current_user.rol.nombre_rol.lower() not in ["administrador", "supervisor"]:
        raise HTTPException(status_code=403, detail="No tienes permisos para desasignar puntos.")
    punto = db.query(PuntoReposicion).filter(PuntoReposicion.id_punto == id_punto).first()
    if not punto:
        raise HTTPException(status_code=404, detail="Punto de reposición no encontrado.")
    if not punto.id_usuario:
        raise HTTPException(status_code=404, detail="El punto no está asignado a ningún usuario.")
    punto.id_usuario = None
    db.commit()
    db.refresh(punto)
    return {"mensaje": "Punto desasignado correctamente."}

@router.put("/puntos/{id_punto}/asignar-producto", response_model=PuntoReposicionOut)
def asignar_producto_a_punto(
    id_punto: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    print(f" [INICIO] Endpoint asignar-producto llamado:")
    print(f"   - id_punto: {id_punto}")
    print(f"   - body: {body}")
    print(f"   - current_user: {current_user.nombre if current_user else 'None'}")
    print(f"   - user_role: {current_user.rol.nombre_rol if current_user and current_user.rol else 'None'}")
    
    try:
        id_producto = body.get("id_producto")
        print(f"   - id_producto extraído: {id_producto} (tipo: {type(id_producto)})")
        print(f"   - El supervisor se obtendrá automáticamente del producto")
        
        if not id_producto:
            print(" Error: Falta el ID del producto")
            raise HTTPException(status_code=400, detail="Falta el ID del producto.")
        
        if current_user.rol.nombre_rol not in [RolEnum.ADMINISTRADOR.value, RolEnum.SUPERVISOR.value]:
            print(f" Error: Usuario no autorizado - rol: {current_user.rol.nombre_rol}")
            raise HTTPException(status_code=403, detail="No autorizado.")

        # Verificar que el producto existe y obtener el supervisor asignado
        producto = db.query(Producto).filter(Producto.id_producto == id_producto).first()
        if not producto:
            print(f" Error: Producto {id_producto} no encontrado")
            raise HTTPException(status_code=404, detail=f"Producto con ID {id_producto} no encontrado.")
        print(f" Producto encontrado: {producto.nombre}")
        
        # Obtener el supervisor asignado al producto
        id_usuario_supervisor = producto.id_usuario
        print(f" Supervisor asignado al producto: {id_usuario_supervisor}")

        # Verificar que el supervisor existe
        supervisor = db.query(Usuario).filter(Usuario.id_usuario == id_usuario_supervisor).first()
        if not supervisor:
            print(f" Error: Supervisor {id_usuario_supervisor} no encontrado")
            raise HTTPException(status_code=404, detail=f"Supervisor con ID {id_usuario_supervisor} no encontrado.")
        print(f" Supervisor encontrado: {supervisor.nombre}")

        # Asignar producto y usuario al punto
        punto = db.query(PuntoReposicion).filter(PuntoReposicion.id_punto == id_punto).first()
        if not punto:
            print(f" Error: Punto {id_punto} no encontrado")
            raise HTTPException(status_code=404, detail="Punto de reposición no encontrado.")
        
        print(f" Punto encontrado: {punto.id_punto} (mueble: {punto.id_mueble}, nivel: {punto.nivel}, estanteria: {punto.estanteria})")
        
        # Guardar estado anterior para logging
        producto_anterior = punto.id_producto
        usuario_anterior = punto.id_usuario
        
        punto.id_producto = id_producto
        punto.id_usuario = id_usuario_supervisor  # Asignar el supervisor del producto, no el administrador
        db.commit()
        db.refresh(punto)
        print(f" Producto asignado exitosamente:")
        print(f"   - Producto anterior: {producto_anterior} -> Nuevo: {punto.id_producto}")
        print(f"   - Usuario anterior: {usuario_anterior} -> Nuevo: {punto.id_usuario} (supervisor del producto)")

        # Construir respuesta como antes
        producto_final = db.query(Producto).filter(Producto.id_producto == punto.id_producto).first() if punto.id_producto else None
        producto_out = None
        if producto_final:
            producto_out = ProductoAsociado(
                nombre=producto_final.nombre,
                categoria=producto_final.categoria,
                unidad_tipo=producto_final.unidad_tipo,
                unidad_cantidad=producto_final.unidad_cantidad
            )
        
        response = PuntoReposicionOut(
            id_punto=punto.id_punto,
            id_mueble=punto.id_mueble,
            nivel=punto.nivel,
            estanteria=punto.estanteria,
            producto=producto_out
        )
        print(f" [FIN] Respuesta construida exitosamente: {response}")
        return response
        
    except HTTPException as e:
        print(f" HTTPException capturada: {e.status_code} - {e.detail}")
        raise e
    except Exception as e:
        print(f" Error inesperado: {type(e).__name__}: {str(e)}")
        import traceback
        print(f" Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@router.delete("/puntos/{id_punto}/desasignar-producto", response_model=PuntoReposicionOut)
def desasignar_producto_punto(
    id_punto: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if current_user.rol.nombre_rol not in [RolEnum.ADMINISTRADOR.value, RolEnum.SUPERVISOR.value]:
        raise HTTPException(status_code=403, detail="Solo administradores o supervisores pueden desasignar productos de puntos.")
    try:
        punto = desasignar_producto_de_punto(db, id_punto)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PuntoReposicionOut(
        id_punto=punto.id_punto,
        id_mueble=punto.id_mueble,
        nivel=punto.nivel,
        estanteria=punto.estanteria,
        producto=None
    )

@router.post("/mapas", status_code=201)
def crear_mapa(
    body: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    nombre = body.get("nombre")
    ancho = body.get("ancho")
    alto = body.get("alto")
    if not nombre or not isinstance(ancho, int) or not isinstance(alto, int) or ancho <= 0 or alto <= 0:
        raise HTTPException(status_code=422, detail="nombre, ancho y alto son requeridos y deben ser mayores a cero.")
    # Validar duplicidad de nombre EN LA MISMA EMPRESA
    existe = db.query(Mapa).filter(
        Mapa.nombre == nombre,
        Mapa.id_empresa == current_user.id_empresa
    ).first()
    if existe:
        raise HTTPException(status_code=409, detail="Ya existe un mapa con ese nombre en esta empresa.")
    try:
        # 1. Crear el mapa (inactivo por defecto)
        mapa = Mapa(
            nombre=nombre,
            ancho=ancho,
            alto=alto,
            id_empresa=current_user.id_empresa,
            activo=False
        )
        db.add(mapa)
        db.flush()  # Obtener id_mapa

        # 2. Inicializar la grilla con objeto "Suelo Base" (tipo Pasillo)
        tipo_pasillo = db.query(ObjetoTipo).filter(ObjetoTipo.nombre_tipo.ilike("pasillo")).first()
        id_tipo_pasillo = tipo_pasillo.id_tipo if tipo_pasillo else 1  # Fallback a 1

        obj_suelo = db.query(ObjetoMapa).filter(
            ObjetoMapa.id_empresa == current_user.id_empresa,
            ObjetoMapa.nombre == "Suelo Base",
            ObjetoMapa.id_tipo == id_tipo_pasillo
        ).first()

        if not obj_suelo:
            obj_suelo = ObjetoMapa(
                nombre="Suelo Base",
                id_tipo=id_tipo_pasillo,
                id_empresa=current_user.id_empresa
            )
            db.add(obj_suelo)
            db.flush()

        # Insertar grilla completa con Suelo Base
        ubicaciones_objs = []
        ubicaciones_resp = []
        for x in range(ancho):
            for y in range(alto):
                ubicaciones_objs.append(UbicacionFisica(
                    id_mapa=mapa.id_mapa,
                    x=x,
                    y=y,
                    id_objeto=obj_suelo.id_objeto
                ))
                ubicaciones_resp.append({"x": x, "y": y})
        db.bulk_save_objects(ubicaciones_objs)

        # 3. Asegurar "Muro Estándar" (tipo Pared) para la empresa
        tipo_pared = db.query(ObjetoTipo).filter(ObjetoTipo.nombre_tipo.ilike("muro")).first()
        if tipo_pared:
            muro_existente = db.query(ObjetoMapa).filter(
                ObjetoMapa.id_empresa == current_user.id_empresa,
                ObjetoMapa.id_tipo == tipo_pared.id_tipo,
                ObjetoMapa.nombre == "Muro Estándar"
            ).first()
            if not muro_existente:
                muro_nuevo = ObjetoMapa(
                    nombre="Muro Estándar",
                    id_tipo=tipo_pared.id_tipo,
                    id_empresa=current_user.id_empresa
                )
                db.add(muro_nuevo)
        # [NUEVO] Lógica: Asegurar objeto y tipo 'Salida'
        tipo_salida = db.query(ObjetoTipo).filter(ObjetoTipo.nombre_tipo.ilike("salida")).first()
        if not tipo_salida:
            tipo_salida = ObjetoTipo(nombre_tipo="salida", caminable=True, destino=False)
            db.add(tipo_salida)
            db.flush()
        obj_salida = db.query(ObjetoMapa).filter(
            ObjetoMapa.id_empresa == current_user.id_empresa,
            ObjetoMapa.id_tipo == tipo_salida.id_tipo
        ).first()
        if not obj_salida:
            obj_salida = ObjetoMapa(
                nombre="Salida / Entrada",
                id_tipo=tipo_salida.id_tipo,
                id_empresa=current_user.id_empresa
            )
            db.add(obj_salida)

        db.commit()
        db.refresh(mapa)
        return {
            "id_mapa": mapa.id_mapa,
            "nombre": mapa.nombre,
            "ancho": mapa.ancho,
            "alto": mapa.alto,
            "activo": mapa.activo,
            "total_ubicaciones": len(ubicaciones_resp),
            "ubicaciones": ubicaciones_resp
        }
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear mapa o ubicaciones: {str(e)}")


@router.get("/mapa/supervisor/vista", response_model=MapeoReposicionResponse)
def visualizar_mapa_supervisor(
    id_mapa: int = Query(None, description="ID del mapa a consultar (opcional)"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if current_user.rol.nombre_rol.lower() != "supervisor":
        raise HTTPException(status_code=403, detail="Solo los supervisores pueden acceder a este recurso.")

    from app.models.supervision import Supervision

    # Obtener ids de puntos asignados al supervisor y sus reponedores
    puntos_usuario = db.query(PuntoReposicion.id_punto).filter(PuntoReposicion.id_usuario == current_user.id_usuario).all()
    puntos_usuario_ids = [p[0] for p in puntos_usuario]

    reponedores = db.query(Supervision.reponedor_id).filter(Supervision.supervisor_id == current_user.id_usuario).all()
    reponedor_ids = [r[0] for r in reponedores]

    puntos_reponedores = []
    if reponedor_ids:
        puntos_reponedores = db.query(PuntoReposicion.id_punto).filter(PuntoReposicion.id_usuario.in_(reponedor_ids)).all()
    puntos_reponedores_ids = [p[0] for p in puntos_reponedores]

    puntos_ids_permitidos = set(puntos_usuario_ids + puntos_reponedores_ids)

    # Seleccionar el mapa
    # Selección de mapa filtrando SIEMPRE por empresa del usuario
    if id_mapa is None:
        mapa = db.query(Mapa).filter(
            Mapa.id_empresa == current_user.id_empresa,
            Mapa.activo == True
        ).first()
    else:
        mapa = db.query(Mapa).filter(
            Mapa.id_mapa == id_mapa,
            Mapa.id_empresa == current_user.id_empresa,
            Mapa.activo == True
        ).first()
    if not mapa:
        return {"mensaje": "No hay mapas registrados.", "mapa": None, "ubicaciones": []}
    ubicaciones_db = db.query(UbicacionFisica).filter(UbicacionFisica.id_mapa == mapa.id_mapa).all()
    if not ubicaciones_db:
        return {"mensaje": "No hay ubicaciones cargadas.", "mapa": MapaOut(id=mapa.id_mapa, nombre=mapa.nombre, ancho=mapa.ancho, alto=mapa.alto), "ubicaciones": []}
    ubicaciones = []
    for ubic in ubicaciones_db:
        objeto = db.query(ObjetoMapa).filter(ObjetoMapa.id_objeto == ubic.id_objeto).first() if ubic.id_objeto else None
        objeto_out = None
        mueble_out = None
        if objeto:
            tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == objeto.id_tipo).first()
            objeto_out = ObjetoOut(
                nombre=objeto.nombre,
                tipo=tipo.nombre_tipo if tipo else "",
                caminable=tipo.caminable if tipo else None
            )
            mueble = db.query(MuebleReposicion).filter(MuebleReposicion.id_objeto == objeto.id_objeto).first()
            if mueble:
                puntos_db = db.query(PuntoReposicion).filter(PuntoReposicion.id_mueble == mueble.id_mueble).all()
                puntos_out = []
                for punto in puntos_db:
                    # Solo mostrar detalles si el punto pertenece al supervisor o sus reponedores
                    producto_out = None
                    if punto.id_punto in puntos_ids_permitidos:
                        producto = db.query(Producto).filter(Producto.id_producto == punto.id_producto).first() if punto.id_producto else None
                        if producto:
                            producto_out = ProductoAsociado(
                                nombre=producto.nombre,
                                categoria=producto.categoria,
                                unidad_tipo=producto.unidad_tipo,
                                unidad_cantidad=producto.unidad_cantidad
                            )
                    puntos_out.append(PuntoReposicionOut(
                        id_punto=punto.id_punto,
                        id_mueble=punto.id_mueble,
                        nivel=punto.nivel,
                        estanteria=punto.estanteria,
                        producto=producto_out
                    ))
                mueble_out = MuebleOut(
                    filas=mueble.filas,
                    columnas=mueble.columnas,
                    puntos_reposicion=puntos_out
                )
        ubicaciones.append(UbicacionOut(
            x=ubic.x,
            y=ubic.y,
            objeto=objeto_out,
            mueble=mueble_out
        ))
    return {
        "mapa": MapaOut(id=mapa.id_mapa, nombre=mapa.nombre, ancho=mapa.ancho, alto=mapa.alto),
        "ubicaciones": ubicaciones
    }


@router.get("/mapa/reponedor/vista", response_model=MapeoReposicionResponse)
def visualizar_mapa_reponedor(
    id_mapa: int = Query(None, description="ID del mapa a consultar (opcional)"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if current_user.rol.nombre_rol.lower() != "reponedor":
        raise HTTPException(status_code=403, detail="Solo los reponedores pueden acceder a este recurso.")

    puntos_usuario = db.query(PuntoReposicion.id_punto).filter(PuntoReposicion.id_usuario == current_user.id_usuario).all()
    puntos_ids_permitidos = set([p[0] for p in puntos_usuario])

    # Seleccionar el mapa
    # Selección de mapa filtrando SIEMPRE por empresa del usuario
    if id_mapa is None:
        mapa = db.query(Mapa).filter(
            Mapa.id_empresa == current_user.id_empresa,
            Mapa.activo == True
        ).first()
    else:
        mapa = db.query(Mapa).filter(
            Mapa.id_mapa == id_mapa,
            Mapa.id_empresa == current_user.id_empresa,
            Mapa.activo == True
        ).first()
    if not mapa:
        return {"mensaje": "No hay mapas registrados.", "mapa": None, "ubicaciones": []}
    ubicaciones_db = db.query(UbicacionFisica).filter(UbicacionFisica.id_mapa == mapa.id_mapa).all()
    if not ubicaciones_db:
        return {"mensaje": "No hay ubicaciones cargadas.", "mapa": MapaOut(id=mapa.id_mapa, nombre=mapa.nombre, ancho=mapa.ancho, alto=mapa.alto), "ubicaciones": []}
    ubicaciones = []
    for ubic in ubicaciones_db:
        objeto = db.query(ObjetoMapa).filter(ObjetoMapa.id_objeto == ubic.id_objeto).first() if ubic.id_objeto else None
        objeto_out = None
        mueble_out = None
        if objeto:
            tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == objeto.id_tipo).first()
            objeto_out = ObjetoOut(
                nombre=objeto.nombre,
                tipo=tipo.nombre_tipo if tipo else "",
                caminable=tipo.caminable if tipo else None
            )
            mueble = db.query(MuebleReposicion).filter(MuebleReposicion.id_objeto == objeto.id_objeto).first()
            if mueble:
                puntos_db = db.query(PuntoReposicion).filter(PuntoReposicion.id_mueble == mueble.id_mueble).all()
                puntos_out = []
                for punto in puntos_db:
                    producto_out = None
                    if punto.id_punto in puntos_ids_permitidos:
                        producto = db.query(Producto).filter(Producto.id_producto == punto.id_producto).first() if punto.id_producto else None
                        if producto:
                            producto_out = ProductoAsociado(
                                nombre=producto.nombre,
                                categoria=producto.categoria,
                                unidad_tipo=producto.unidad_tipo,
                                unidad_cantidad=producto.unidad_cantidad
                            )
                    puntos_out.append(PuntoReposicionOut(
                        id_punto=punto.id_punto,
                        id_mueble=punto.id_mueble,
                        nivel=punto.nivel,
                        estanteria=punto.estanteria,
                        producto=producto_out
                    ))
                mueble_out = MuebleOut(
                    filas=mueble.filas,
                    columnas=mueble.columnas,
                    puntos_reposicion=puntos_out
                )
        ubicaciones.append(UbicacionOut(
            x=ubic.x,
            y=ubic.y,
            objeto=objeto_out,
            mueble=mueble_out
        ))
    return {
        "mapa": MapaOut(id=mapa.id_mapa, nombre=mapa.nombre, ancho=mapa.ancho, alto=mapa.alto),
        "ubicaciones": ubicaciones
    }


@router.get("/mapa/activo", status_code=200)
def obtener_mapa_activo(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene el mapa actualmente activo.
    """
    if not current_user or current_user.rol.nombre_rol != RolEnum.ADMINISTRADOR.value:
        raise HTTPException(status_code=403, detail="Solo administradores pueden consultar el mapa activo.")
    
    mapa_activo = db.query(Mapa).filter(
        Mapa.activo == True,
        Mapa.id_empresa == current_user.id_empresa
    ).first()
    
    if not mapa_activo:
        return {
            "mensaje": "No hay mapa activo configurado.",
            "mapa": None
        }
    
    return {
        "mensaje": "Mapa activo encontrado.",
        "mapa": {
            "id_mapa": mapa_activo.id_mapa,
            "nombre": mapa_activo.nombre,
            "ancho": mapa_activo.ancho,
            "alto": mapa_activo.alto,
            "activo": mapa_activo.activo
        }
    }

@router.get("/mapa/objetos", response_model=List[ObjetoListadoOut])
def listar_objetos_mapa(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista todos los objetos disponibles para la empresa del usuario con su tipo.
    Incluye 'Suelo Base' y 'Muro Estándar' si existen.
    """
    if not current_user or current_user.rol.nombre_rol not in [RolEnum.ADMINISTRADOR.value, RolEnum.SUPERVISOR.value]:
        raise HTTPException(status_code=403, detail="No autorizado para listar objetos del mapa.")
    objetos = db.query(ObjetoMapa).filter(ObjetoMapa.id_empresa == current_user.id_empresa).all()
    tipos_cache = {}
    resultado = []
    for obj in objetos:
        if obj.id_tipo not in tipos_cache:
            tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == obj.id_tipo).first()
            tipos_cache[obj.id_tipo] = tipo
        tipo = tipos_cache.get(obj.id_tipo)
        resultado.append(ObjetoListadoOut(
            id_objeto=obj.id_objeto,
            nombre=obj.nombre,
            tipo=ObjetoTipoListadoOut(
                id=tipo.id_tipo if tipo else 0,
                nombre=tipo.nombre_tipo if tipo else "",
                caminable=tipo.caminable if tipo else None
            )
        ))
    return resultado

#danko te odio aqui ta tu endpoint pa que deji de llorar
@router.get("/mapa/{id_mapa}/objetos", response_model=List[ObjetoListadoOut])
def listar_objetos_por_mapa(
    id_mapa: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Lista solo los objetos presentes en el `id_mapa` indicado
    y pertenecientes a la empresa del usuario.

    - No depende de que el mapa esté activo.
    - Usa `UbicacionFisica` para obtener los `id_objeto` colocados en el mapa.
    """
    if not current_user or current_user.rol.nombre_rol not in [RolEnum.ADMINISTRADOR.value, RolEnum.SUPERVISOR.value]:
        raise HTTPException(status_code=403, detail="No autorizado para listar objetos del mapa.")

    # Validar que el mapa exista y pertenezca a la empresa del usuario
    mapa = db.query(Mapa).filter(
        Mapa.id_mapa == id_mapa,
        Mapa.id_empresa == current_user.id_empresa
    ).first()
    if not mapa:
        raise HTTPException(status_code=404, detail="Mapa no encontrado para tu empresa.")

    # Obtener id_objeto presentes en el mapa
    ubicaciones = db.query(UbicacionFisica.id_objeto).filter(
        UbicacionFisica.id_mapa == id_mapa,
        UbicacionFisica.id_objeto.isnot(None)
    ).all()
    ids_objetos = list({row[0] for row in ubicaciones if row[0] is not None})

    if not ids_objetos:
        return []

    # Identificar tipos base que deben verse siempre: pasillo, muro y salida
    tipo_pasillo = db.query(ObjetoTipo).filter(ObjetoTipo.nombre_tipo.ilike("pasillo")).first()
    tipo_muro = db.query(ObjetoTipo).filter(ObjetoTipo.nombre_tipo.ilike("muro")).first()
    tipo_salida = db.query(ObjetoTipo).filter(ObjetoTipo.nombre_tipo.ilike("salida")).first()
    tipos_base_ids = [t.id_tipo for t in [tipo_pasillo, tipo_muro, tipo_salida] if t]

    # Traer objetos de la empresa cumpliendo:
    # - Muebles (id_tipo == 3) SOLO si están presentes en el mapa (ids_objetos)
    # - Tipos base (pasillo/muro/salida) SIEMPRE
    query = db.query(ObjetoMapa).filter(ObjetoMapa.id_empresa == current_user.id_empresa)

    # Construir condición OR: (muebles en mapa) OR (tipos base)
    from sqlalchemy import or_, and_
    condicion_muebles_en_mapa = and_(ObjetoMapa.id_tipo == 3, ObjetoMapa.id_objeto.in_(ids_objetos)) if ids_objetos else and_(ObjetoMapa.id_tipo == 3, False)
    condicion_tipos_base = ObjetoMapa.id_tipo.in_(tipos_base_ids) if tipos_base_ids else and_(False)

    objetos = query.filter(or_(condicion_muebles_en_mapa, condicion_tipos_base)).all()

    # Cache de tipos para evitar N+1
    tipos_cache = {}
    resultado = []
    for obj in objetos:
        if obj.id_tipo not in tipos_cache:
            tipo = db.query(ObjetoTipo).filter(ObjetoTipo.id_tipo == obj.id_tipo).first()
            tipos_cache[obj.id_tipo] = tipo
        tipo = tipos_cache.get(obj.id_tipo)
        resultado.append(ObjetoListadoOut(
            id_objeto=obj.id_objeto,
            nombre=obj.nombre,
            tipo=ObjetoTipoListadoOut(
                id=tipo.id_tipo if tipo else 0,
                nombre=tipo.nombre_tipo if tipo else "",
                caminable=tipo.caminable if tipo else None
            )
        ))
    return resultado

@router.post("/{id_mapa}/guardar-layout-completo")
def guardar_layout_completo(
    id_mapa: int,
    layout_in: LayoutCompletoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Guarda el layout actualizando posiciones de objetos EXISTENTES.
    Valida que exista exactamente una 'Salida'.
    """
    mapa = db.query(Mapa).filter(Mapa.id_mapa == id_mapa, Mapa.id_empresa == current_user.id_empresa).first()
    if not mapa:
        raise HTTPException(status_code=404, detail="Mapa no encontrado")

    try:
        tipo_salida = db.query(ObjetoTipo).filter(ObjetoTipo.nombre_tipo.ilike("salida")).first()
        if not tipo_salida:
            raise HTTPException(status_code=500, detail="Error config: Tipo 'salida' no existe.")

        ids_usados = list(set([u.id_objeto_real for u in layout_in.ubicaciones]))
        if not ids_usados:
            raise HTTPException(status_code=422, detail="El mapa no puede estar vacío, debe tener al menos una Salida.")

        objetos_db = db.query(ObjetoMapa).filter(ObjetoMapa.id_objeto.in_(ids_usados)).all()
        tipo_por_objeto = {obj.id_objeto: obj.id_tipo for obj in objetos_db}

        objetos_salida_distintos = set()
        for id_obj in ids_usados:
            if tipo_por_objeto.get(id_obj) == tipo_salida.id_tipo:
                objetos_salida_distintos.add(id_obj)

        if len(objetos_salida_distintos) == 0:
            raise HTTPException(status_code=422, detail="El mapa debe tener obligatoriamente una 'Salida'.")
        if len(objetos_salida_distintos) > 1:
            raise HTTPException(status_code=422, detail="El mapa solo puede tener una única 'Salida'.")

        # Limpiar asignaciones previas
        db.query(UbicacionFisica).filter(UbicacionFisica.id_mapa == id_mapa).update({UbicacionFisica.id_objeto: None})

        # Actualizar nuevas ubicaciones
        for ubic in layout_in.ubicaciones:
            if ubic.id_objeto_real not in tipo_por_objeto:
                continue
            celda = db.query(UbicacionFisica).filter(
                UbicacionFisica.id_mapa == id_mapa,
                UbicacionFisica.x == ubic.x,
                UbicacionFisica.y == ubic.y
            ).first()
            if celda:
                celda.id_objeto = ubic.id_objeto_real

        db.commit()
        return {"mensaje": "Layout actualizado correctamente"}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar layout: {str(e)}")
