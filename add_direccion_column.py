"""
Script para agregar la columna 'direccion' a la tabla mueble_reposicion
Ejecutar: python add_direccion_column.py
"""
from app.core.database.database import Database
from sqlalchemy import text

def add_direccion_column():
    database = Database()
    db = next(database.get_db())
    
    try:
        print("🔧 Agregando columna 'direccion' a tabla mueble_reposicion...")
        
        # Agregar columna si no existe
        db.execute(text("""
            ALTER TABLE mueble_reposicion 
            ADD COLUMN IF NOT EXISTS direccion VARCHAR(1) DEFAULT 'T';
        """))
        
        db.commit()
        print("✅ Columna 'direccion' agregada exitosamente")
        print("   Valores posibles: 'N' (Norte), 'S' (Sur), 'E' (Este), 'O' (Oeste), 'T' (Todos)")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_direccion_column()
