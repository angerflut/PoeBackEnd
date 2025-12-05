"""
Script para crear un usuario SuperAdmin para el Backoffice
Ejecutar: python crear_superadmin.py
"""
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from app.core.database.database import Database
from app.models.usuario import Usuario, Rol
from app.core.security.password import get_password_hash
from sqlalchemy import text

def crear_superadmin():
    db_instance = Database()
    db = db_instance.SessionLocal()
    
    try:
        print("=" * 60)
        print("🔐 CREAR USUARIO SUPERADMIN PARA BACKOFFICE")
        print("=" * 60)
        
        # Verificar si el rol SuperAdmin existe
        rol_superadmin = db.query(Rol).filter(Rol.nombre_rol == "SuperAdmin").first()
        
        if not rol_superadmin:
            print("\n❌ El rol 'SuperAdmin' no existe en la base de datos.")
            print("   Creando el rol SuperAdmin...")
            
            # Crear el rol SuperAdmin
            rol_superadmin = Rol(nombre_rol="SuperAdmin")
            db.add(rol_superadmin)
            db.commit()
            db.refresh(rol_superadmin)
            print(f"✅ Rol 'SuperAdmin' creado con ID: {rol_superadmin.id_rol}")
        else:
            print(f"✅ Rol 'SuperAdmin' encontrado con ID: {rol_superadmin.id_rol}")
        
        # Verificar si ya existe un SuperAdmin
        superadmin_existente = db.query(Usuario).filter(
            Usuario.correo == "superadmin@poe.com"
        ).first()
        
        if superadmin_existente:
            print("\n⚠️  Ya existe un usuario SuperAdmin con el correo 'superadmin@poe.com'")
            respuesta = input("¿Desea actualizar la contraseña? (s/n): ")
            
            if respuesta.lower() == 's':
                nueva_contraseña = input("Ingrese la nueva contraseña (o presione Enter para usar 'SuperAdmin123!'): ")
                if not nueva_contraseña:
                    nueva_contraseña = "SuperAdmin123!"
                
                superadmin_existente.contraseña = get_password_hash(nueva_contraseña)
                db.commit()
                print(f"✅ Contraseña actualizada para {superadmin_existente.nombre}")
                print(f"\n📧 Correo: superadmin@poe.com")
                print(f"🔑 Contraseña: {nueva_contraseña}")
            else:
                print("❌ Operación cancelada.")
        else:
            print("\n📝 Creando nuevo usuario SuperAdmin...")
            
            # Verificar si existe al menos una empresa
            resultado = db.execute(text("SELECT id_empresa FROM empresa LIMIT 1"))
            primera_empresa = resultado.fetchone()
            
            if not primera_empresa:
                print("❌ No hay empresas en la base de datos.")
                print("   Creando empresa por defecto...")
                
                # Crear una empresa por defecto para el SuperAdmin
                db.execute(text("""
                    INSERT INTO empresa (nombre_empresa, rut_empresa, direccion, ciudad, region, estado)
                    VALUES ('POE System Admin', '99999999-9', 'Oficina Central', 'Santiago', 'Metropolitana', 'activo')
                """))
                db.commit()
                
                resultado = db.execute(text("SELECT id_empresa FROM empresa WHERE rut_empresa = '99999999-9'"))
                primera_empresa = resultado.fetchone()
                print(f"✅ Empresa creada con ID: {primera_empresa[0]}")
            
            id_empresa = primera_empresa[0]
            
            # Solicitar información del SuperAdmin
            nombre = input("Ingrese el nombre del SuperAdmin (o presione Enter para 'Super Admin POE'): ")
            if not nombre:
                nombre = "Super Admin POE"
            
            correo = input("Ingrese el correo (o presione Enter para 'superadmin@poe.com'): ")
            if not correo:
                correo = "superadmin@poe.com"
            
            contraseña = input("Ingrese la contraseña (o presione Enter para 'SuperAdmin123!'): ")
            if not contraseña:
                contraseña = "SuperAdmin123!"
            
            # Crear el hash de la contraseña
            password_hash = get_password_hash(contraseña)
            
            # Crear el usuario SuperAdmin
            nuevo_superadmin = Usuario(
                nombre=nombre,
                correo=correo,
                contraseña=password_hash,
                rol_id=rol_superadmin.id_rol,
                estado="activo",
                id_empresa=id_empresa
            )
            
            db.add(nuevo_superadmin)
            db.commit()
            db.refresh(nuevo_superadmin)
            
            print("\n" + "=" * 60)
            print("✅ USUARIO SUPERADMIN CREADO EXITOSAMENTE")
            print("=" * 60)
            print(f"\n👤 ID Usuario: {nuevo_superadmin.id_usuario}")
            print(f"📧 Correo: {correo}")
            print(f"🔑 Contraseña: {contraseña}")
            print(f"🏢 Empresa ID: {id_empresa}")
            print(f"🎭 Rol: SuperAdmin (ID: {rol_superadmin.id_rol})")
            print(f"✨ Estado: {nuevo_superadmin.estado}")
            print("\n" + "=" * 60)
            print("🌐 URL de acceso: http://localhost:5173/login")
            print("📋 Después del login, serás redirigido a: /backoffice")
            print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    crear_superadmin()
