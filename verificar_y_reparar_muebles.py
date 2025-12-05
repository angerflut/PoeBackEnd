"""
Script para verificar y reparar muebles sin puntos de reposición.
Este script identifica muebles en la base de datos que no tienen puntos de reposición
y los genera automáticamente.

Uso: python verificar_y_reparar_muebles.py
"""

from app.core.database.database import db
from app.models.mueble_reposicion import MuebleReposicion
from app.models.objeto_mapa import ObjetoMapa
from app.models.punto_reposicion import PuntoReposicion
from app.repositories import punto_reposicion as punto_reposicion_repository
from sqlalchemy import func

def verificar_y_reparar_muebles():
    """
    Verifica todos los muebles y repara aquellos que no tienen puntos de reposición.
    """
    session = db.SessionLocal()
    try:
        print("=" * 80)
        print("VERIFICACIÓN Y REPARACIÓN DE MUEBLES")
        print("=" * 80)
        
        # Obtener todos los muebles de reposición
        muebles = session.query(MuebleReposicion).all()
        print(f"\n📊 Total de muebles de reposición en la base de datos: {len(muebles)}")
        
        if not muebles:
            print("\n✅ No hay muebles de reposición en la base de datos.")
            return
        
        # Verificar cada mueble
        muebles_sin_puntos = []
        muebles_con_puntos = []
        
        for mueble in muebles:
            # Obtener información del objeto
            objeto = session.query(ObjetoMapa).filter(
                ObjetoMapa.id_objeto == mueble.id_objeto
            ).first()
            
            # Contar puntos de reposición
            puntos_count = session.query(func.count(PuntoReposicion.id_punto)).filter(
                PuntoReposicion.id_mueble == mueble.id_mueble
            ).scalar()
            
            capacidad_esperada = mueble.filas * mueble.columnas
            
            info = {
                'id_mueble': mueble.id_mueble,
                'id_objeto': mueble.id_objeto,
                'nombre': objeto.nombre if objeto else "Sin nombre",
                'filas': mueble.filas,
                'columnas': mueble.columnas,
                'capacidad_esperada': capacidad_esperada,
                'puntos_actuales': puntos_count,
                'id_empresa': mueble.id_empresa
            }
            
            if puntos_count == 0:
                muebles_sin_puntos.append(info)
            else:
                muebles_con_puntos.append(info)
        
        # Mostrar resumen
        print(f"\n✅ Muebles con puntos de reposición: {len(muebles_con_puntos)}")
        print(f"⚠️  Muebles SIN puntos de reposición: {len(muebles_sin_puntos)}")
        
        # Mostrar detalle de muebles con puntos
        if muebles_con_puntos:
            print("\n" + "=" * 80)
            print("MUEBLES CON PUNTOS DE REPOSICIÓN")
            print("=" * 80)
            for info in muebles_con_puntos:
                print(f"\n✅ Mueble: {info['nombre']}")
                print(f"   ID Mueble: {info['id_mueble']} | ID Objeto: {info['id_objeto']}")
                print(f"   Dimensiones: {info['filas']}x{info['columnas']} = {info['capacidad_esperada']} puntos")
                print(f"   Puntos generados: {info['puntos_actuales']}")
                print(f"   Empresa: {info['id_empresa']}")
        
        # Mostrar detalle de muebles sin puntos
        if muebles_sin_puntos:
            print("\n" + "=" * 80)
            print("MUEBLES SIN PUNTOS DE REPOSICIÓN (REQUIEREN REPARACIÓN)")
            print("=" * 80)
            for info in muebles_sin_puntos:
                print(f"\n⚠️  Mueble: {info['nombre']}")
                print(f"   ID Mueble: {info['id_mueble']} | ID Objeto: {info['id_objeto']}")
                print(f"   Dimensiones: {info['filas']}x{info['columnas']} = {info['capacidad_esperada']} puntos esperados")
                print(f"   Puntos actuales: {info['puntos_actuales']} ❌")
                print(f"   Empresa: {info['id_empresa']}")
            
            # Preguntar si desea reparar
            print("\n" + "=" * 80)
            respuesta = input("\n¿Desea generar los puntos de reposición faltantes? (S/N): ").strip().upper()
            
            if respuesta == 'S':
                print("\n🔧 Generando puntos de reposición...")
                
                for info in muebles_sin_puntos:
                    try:
                        print(f"\n   Generando puntos para: {info['nombre']} ({info['filas']}x{info['columnas']})...")
                        
                        punto_reposicion_repository.generar_puntos_mueble(
                            session,
                            info['id_mueble'],
                            info['filas'],
                            info['columnas'],
                            info['id_empresa']
                        )
                        
                        print(f"   ✅ {info['capacidad_esperada']} puntos generados exitosamente")
                        
                    except Exception as e:
                        print(f"   ❌ Error al generar puntos para {info['nombre']}: {str(e)}")
                
                session.commit()
                print("\n✅ Reparación completada. Todos los muebles ahora tienen puntos de reposición.")
            else:
                print("\n❌ Reparación cancelada. Los muebles no fueron modificados.")
        
        print("\n" + "=" * 80)
        print("VERIFICACIÓN COMPLETADA")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error durante la verificación: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    try:
        verificar_y_reparar_muebles()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación cancelada por el usuario.")
    except Exception as e:
        print(f"\n❌ Error fatal: {str(e)}")
