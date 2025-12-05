"""
Script para reiniciar todas las tareas a estado 'Pendiente'
"""
from app.core.database.database import Database
from sqlalchemy import text

def reset_tasks():
    database = Database()
    db = next(database.get_db())
    
    try:
        # Reiniciar tareas a estado Pendiente
        result = db.execute(text("""
            UPDATE tarea 
            SET estado_id = (SELECT estado_id FROM estado_tarea WHERE nombre_estado = 'pendiente')
            WHERE estado_id IN (
                SELECT estado_id FROM estado_tarea 
                WHERE nombre_estado IN ('en progreso', 'completada')
            )
        """))
        db.commit()
        
        print(f"✅ {result.rowcount} tareas reiniciadas a estado 'Pendiente'")
    finally:
        db.close()

if __name__ == "__main__":
    reset_tasks()


