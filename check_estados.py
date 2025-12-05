"""
Script para verificar los estados de tareas en la base de datos
"""
from app.core.database.database import Database
from sqlalchemy import text

def check_estados():
    database = Database()
    db = next(database.get_db())
    
    try:
        # Ver todos los estados disponibles
        print("📋 Estados disponibles:")
        result = db.execute(text("SELECT estado_id, nombre_estado FROM estado_tarea"))
        for row in result:
            print(f"  - ID: {row[0]}, Nombre: '{row[1]}'")
        
        # Ver el conteo de tareas por estado
        print("\n📊 Tareas por estado:")
        result = db.execute(text("""
            SELECT et.nombre_estado, COUNT(t.id_tarea) as cantidad
            FROM tarea t
            JOIN estado_tarea et ON t.estado_id = et.estado_id
            GROUP BY et.nombre_estado
        """))
        for row in result:
            print(f"  - {row[0]}: {row[1]} tareas")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_estados()
