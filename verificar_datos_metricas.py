#!/usr/bin/env python3
"""
Script para verificar y crear datos de prueba para las métricas del supervisor.
"""

from sqlalchemy.orm import Session
from app.core.database.database import get_db
from app.models.usuario import Usuario, RolEnum
from app.models.tarea import Tarea
from app.models.producto import Producto
from app.models.detalle_tarea import DetalleTarea
from app.models.estado_tarea import EstadoTarea
from sqlalchemy import func
from datetime import datetime, date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verificar_datos():
    """Verifica si hay datos suficientes para las métricas."""
    db: Session = next(get_db())
    
    try:
        # Verificar supervisores
        supervisores = db.query(Usuario).join(Usuario.rol).filter(
            Usuario.rol.has(nombre_rol=RolEnum.SUPERVISOR.value)
        ).all()
        
        logger.info(f"📋 Supervisores encontrados: {len(supervisores)}")
        for sup in supervisores:
            logger.info(f"   - {sup.nombre} (ID: {sup.id_usuario})")
        
        # Verificar reponedores
        reponedores = db.query(Usuario).join(Usuario.rol).filter(
            Usuario.rol.has(nombre_rol=RolEnum.REPONEDOR.value)
        ).all()
        
        logger.info(f"👷 Reponedores encontrados: {len(reponedores)}")
        for rep in reponedores:
            logger.info(f"   - {rep.nombre} (ID: {rep.id_usuario})")
        
        # Verificar productos
        productos = db.query(Producto).all()
        logger.info(f"📦 Productos encontrados: {len(productos)}")
        
        # Verificar tareas
        tareas = db.query(Tarea).all()
        logger.info(f"📋 Tareas encontradas: {len(tareas)}")
        
        # Verificar tareas por supervisor
        if supervisores:
            for supervisor in supervisores:
                tareas_supervisor = db.query(Tarea).filter(
                    Tarea.id_supervisor == supervisor.id_usuario
                ).all()
                logger.info(f"   - Supervisor {supervisor.nombre}: {len(tareas_supervisor)} tareas")
                
                # Verificar estado de las tareas
                for tarea in tareas_supervisor[:5]:  # Solo primeras 5 para no saturar el log
                    logger.info(f"     * Tarea {tarea.id_tarea}: Estado {tarea.estado_id}, Reponedor: {tarea.id_reponedor}")
        
        # Verificar estados de tarea
        estados = db.query(EstadoTarea).all()
        logger.info(f"🏷️ Estados de tarea encontrados: {len(estados)}")
        for estado in estados:
            logger.info(f"   - {estado.nombre_estado} (ID: {estado.id_estado})")
        
        return {
            'supervisores': len(supervisores),
            'reponedores': len(reponedores),
            'productos': len(productos),
            'tareas': len(tareas)
        }
        
    except Exception as e:
        logger.error(f"❌ Error al verificar datos: {str(e)}")
        return None
    finally:
        db.close()

def crear_datos_prueba():
    """Crea datos de prueba si no existen suficientes."""
    db: Session = next(get_db())
    
    try:
        # Verificar si ya hay suficientes datos
        stats = verificar_datos()
        if not stats:
            return False
        
        if stats['tareas'] < 5:
            logger.info("🔧 Creando datos de prueba...")
            
            # Obtener supervisor y reponedor
            supervisor = db.query(Usuario).join(Usuario.rol).filter(
                Usuario.rol.has(nombre_rol=RolEnum.SUPERVISOR.value)
            ).first()
            
            reponedor = db.query(Usuario).join(Usuario.rol).filter(
                Usuario.rol.has(nombre_rol=RolEnum.REPONEDOR.value)
            ).first()
            
            if not supervisor or not reponedor:
                logger.error("❌ No se encontraron supervisor o reponedor para crear datos de prueba")
                return False
            
            # Obtener estados
            estado_pendiente = db.query(EstadoTarea).filter(EstadoTarea.nombre_estado == 'pendiente').first()
            estado_completada = db.query(EstadoTarea).filter(EstadoTarea.nombre_estado == 'completada').first()
            
            if not estado_pendiente or not estado_completada:
                logger.error("❌ No se encontraron estados de tarea necesarios")
                return False
            
            # Crear algunas tareas de prueba
            for i in range(5):
                nueva_tarea = Tarea(
                    descripcion=f"Tarea de prueba {i+1}",
                    fecha_creacion=datetime.now().date(),
                    id_supervisor=supervisor.id_usuario,
                    id_reponedor=reponedor.id_usuario,
                    estado_id=estado_completada.id_estado if i < 3 else estado_pendiente.id_estado  # 3 completadas, 2 pendientes
                )
                db.add(nueva_tarea)
            
            db.commit()
            logger.info("✅ Datos de prueba creados exitosamente")
            return True
        else:
            logger.info("✅ Ya hay suficientes datos en la base de datos")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error al crear datos de prueba: {str(e)}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("🚀 Iniciando verificación de datos para métricas...")
    
    # Verificar datos actuales
    stats = verificar_datos()
    
    if stats:
        logger.info("📊 Resumen de datos:")
        logger.info(f"   - Supervisores: {stats['supervisores']}")
        logger.info(f"   - Reponedores: {stats['reponedores']}")
        logger.info(f"   - Productos: {stats['productos']}")
        logger.info(f"   - Tareas: {stats['tareas']}")
        
        # Crear datos de prueba si es necesario
        if crear_datos_prueba():
            logger.info("✅ Verificación completada exitosamente")
        else:
            logger.error("❌ Error en la verificación")
    else:
        logger.error("❌ Error al verificar datos")
