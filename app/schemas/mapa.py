from pydantic import BaseModel
from typing import List, Optional

class ProductoAsociado(BaseModel):
    nombre: str
    categoria: str
    unidad_tipo: str
    unidad_cantidad: int

class PuntoReposicionOut(BaseModel):
    id_punto: int
    id_mueble: int
    nivel: int
    estanteria: int
    producto: Optional[ProductoAsociado]

class MuebleOut(BaseModel):
    filas: int
    columnas: int
    puntos_reposicion: List[PuntoReposicionOut]

class ObjetoOut(BaseModel):
    nombre: str
    tipo: str
    caminable: Optional[bool]

class UbicacionOut(BaseModel):
    x: int
    y: int
    objeto: Optional[ObjetoOut]
    mueble: Optional[MuebleOut]

class MapaOut(BaseModel):
    id: int
    nombre: str
    ancho: int
    alto: int
    activo: bool = False

class MapeoReposicionResponse(BaseModel):
    mapa: Optional[MapaOut] = None
    ubicaciones: List[UbicacionOut]
    mensaje: Optional[str] = None

# Listado general de objetos del mapa
class ObjetoTipoListadoOut(BaseModel):
    id: int
    nombre: str
    caminable: Optional[bool]

class ObjetoListadoOut(BaseModel):
    id_objeto: int
    nombre: str
    tipo: ObjetoTipoListadoOut

# Inputs para guardar layout completo
class UbicacionInput(BaseModel):
    x: int
    y: int
    id_objeto_real: int

# Eliminado: ObjetoNuevoInput (ya no se crean objetos al vuelo)

class LayoutCompletoCreate(BaseModel):
    ubicaciones: List[UbicacionInput]
