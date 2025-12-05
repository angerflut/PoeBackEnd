"""
Script para limpiar objetos de los mapas (excepto 'Suelo Base')
Útil para resetear mapas de prueba
"""
from app.database import SessionLocal
from app.models.mapa import UbicacionFisica, ObjetoMapa
from sqlalchemy import and_

def limpiar_mapas():
    db = SessionLocal()
    try:
        # Obtener ID del objeto "Suelo Base" (para no eliminarlo)
        suelo_base = db.query(ObjetoMapa).filter(
            ObjetoMapa.nombre == "Suelo Base"
        ).first()
        
        if not suelo_base:
            print("❌ No se encontró 'Suelo Base'")
            return
        
        # Eliminar TODAS las ubicaciones que NO sean "Suelo Base"
        ubicaciones_eliminar = db.query(UbicacionFisica).filter(
            UbicacionFisica.id_objeto != suelo_base.id_objeto
        ).all()
        
        count = len(ubicaciones_eliminar)
        
        for ub in ubicaciones_eliminar:
            db.delete(ub)
        
        db.commit()
        print(f"✅ Se eliminaron {count} objetos de los mapas")
        print("✅ Los mapas ahora están limpios (solo tienen suelo)")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🧹 Limpiando objetos de mapas...")
    limpiar_mapas()
