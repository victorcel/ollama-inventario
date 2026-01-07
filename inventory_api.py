# inventory_api.py
"""
API REST para sistema de inventario con búsqueda semántica
Implementa buenas prácticas de precisión de embeddings
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import ollama
import os
from dotenv import load_dotenv
import logging
from functools import wraps

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
CORS(app)  # Permitir CORS para desarrollo

# Configuración desde variables de entorno
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'inventario'),
    'user': os.getenv('DB_USER', 'inventory_user'),
    'password': os.getenv('DB_PASSWORD', 'changeme_secure_password')
}

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'all-minilm')

# Cliente Ollama configurado
ollama_client = ollama.Client(host=OLLAMA_HOST)


def get_db():
    """Obtener conexión a la base de datos"""
    return psycopg2.connect(**DB_CONFIG)


def handle_errors(f):
    """Decorador para manejo de errores consistente"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except psycopg2.Error as e:
            logger.error(f"Error de base de datos: {e}")
            return jsonify({
                'success': False,
                'error': 'Error de base de datos',
                'detail': str(e)
            }), 500
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            return jsonify({
                'success': False,
                'error': 'Error interno del servidor',
                'detail': str(e)
            }), 500
    return decorated_function


def preparar_texto_embedding(producto):
    """
    Preparar texto optimizado para embedding con mejor precisión

    Aplica las mejores prácticas aprendidas:
    - Repite nombre y categoría para darles más peso
    - Incluye información clave al inicio
    - Usa formato específico para mejor matching

    Args:
        producto (dict): Diccionario con datos del producto

    Returns:
        str: Texto optimizado para generar embedding
    """
    nombre = producto.get('nombre', '')
    categoria = producto.get('categoria', '')
    descripcion = producto.get('descripcion', '')
    codigo = producto.get('codigo', '')
    proveedor = producto.get('proveedor', '')

    # Repetir información clave para aumentar el peso semántico
    texto_parts = [
        f"{nombre}",  # Nombre al inicio (mayor peso)
        f"Producto: {nombre}",  # Repetir nombre con contexto
        f"Categoría: {categoria}" if categoria else "",
        f"Tipo: {categoria}" if categoria else "",  # Repetir categoría
        f"{descripcion}" if descripcion else "",
        f"Código: {codigo}",
        f"Proveedor: {proveedor}" if proveedor else ""
    ]

    return " ".join(filter(None, texto_parts))


def generar_embedding(texto):
    """
    Generar embedding usando Ollama con manejo de errores

    Args:
        texto (str): Texto para generar el embedding

    Returns:
        list: Embedding como lista de floats, o None si hay error
    """
    try:
        response = ollama_client.embed(model=OLLAMA_MODEL, input=texto)
        return response['embeddings'][0]
    except Exception as e:
        logger.error(f"Error generando embedding: {e}")
        return None


@app.route('/api/productos/buscar', methods=['POST'])
@handle_errors
def buscar_productos():
    """
    Búsqueda semántica de productos

    Request JSON:
        {
            "consulta": "laptop Dell XPS",  # Usar términos específicos (marcas, modelos)
            "limite": 10                    # Opcional, default 10
        }

    Response JSON:
        {
            "consulta": "laptop Dell XPS",
            "count": 3,
            "resultados": [...]
        }

    Tips para mejores resultados:
    - Incluir marcas: "Dell", "Logitech", "LG"
    - Ser específico: "laptop" mejor que "computadora"
    - Usar características: "inalámbrico", "RGB", "ergonómico"
    """
    data = request.json
    if not data or 'consulta' not in data:
        return jsonify({
            'success': False,
            'error': 'Falta el campo "consulta"'
        }), 400

    consulta = data.get('consulta', '').strip()
    limite = data.get('limite', 10)

    if not consulta:
        return jsonify({
            'success': False,
            'error': 'La consulta no puede estar vacía'
        }), 400

    logger.info(f"Búsqueda semántica: '{consulta}' (límite: {limite})")

    # Generar embedding de la consulta
    query_embedding = generar_embedding(consulta)

    if not query_embedding:
        return jsonify({
            'success': False,
            'error': 'Error generando embedding de búsqueda'
        }), 500

    # Convertir embedding a formato PostgreSQL
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

    # Buscar en DB
    # NOTA: Aplicamos workaround del bug ORDER BY + LIMIT
    # Obtenemos todos los resultados y limitamos en Python
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT 
            p.id,
            p.codigo,
            p.nombre,
            p.descripcion,
            p.categoria,
            p.precio,
            p.stock,
            pe.embedding <=> %s::vector(384) as distancia
        FROM producto_embeddings pe
        JOIN productos p ON pe.producto_id = p.id
        WHERE p.activo = true
        ORDER BY distancia
    """, (embedding_str,))

    # Obtener todos y limitar en Python (workaround bug ORDER BY + LIMIT)
    todos_resultados = cur.fetchall()
    resultados_limitados = todos_resultados[:limite]

    cur.close()
    conn.close()

    # Formatear resultados
    resultados_formateados = [
        {
            'id': r['id'],
            'codigo': r['codigo'],
            'nombre': r['nombre'],
            'descripcion': r['descripcion'],
            'categoria': r['categoria'],
            'precio': float(r['precio']) if r['precio'] else None,
            'stock': r['stock'],
            'similitud': float(1 - r['distancia'])  # Convertir distancia a similitud
        }
        for r in resultados_limitados
    ]

    logger.info(f"Encontrados {len(resultados_formateados)} resultados")

    return jsonify({
        'success': True,
        'consulta': consulta,
        'count': len(resultados_formateados),
        'total_disponible': len(todos_resultados),
        'resultados': resultados_formateados
    })


@app.route('/api/productos', methods=['GET'])
@handle_errors
def listar_productos():
    """
    Listar productos con paginación

    Query params:
        - page: número de página (default: 1)
        - per_page: resultados por página (default: 20, max: 100)
        - categoria: filtrar por categoría (opcional)
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    categoria = request.args.get('categoria', None)

    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Construir query con filtro opcional
    where_clause = "WHERE activo = true"
    params = []

    if categoria:
        where_clause += " AND categoria = %s"
        params.append(categoria)

    # Contar total
    cur.execute(f"SELECT COUNT(*) as total FROM productos {where_clause}", params)
    total = cur.fetchone()['total']

    # Obtener productos paginados
    params.extend([per_page, offset])
    cur.execute(f"""
        SELECT id, codigo, nombre, descripcion, categoria, 
               precio, stock, ubicacion, proveedor
        FROM productos
        {where_clause}
        ORDER BY nombre
        LIMIT %s OFFSET %s
    """, params)

    productos = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify({
        'success': True,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': (total + per_page - 1) // per_page,
        'productos': [dict(p) for p in productos]
    })


@app.route('/api/productos', methods=['POST'])
@handle_errors
def crear_producto():
    """
    Crear nuevo producto y generar su embedding

    Request JSON:
        {
            "codigo": "PROD-XXX",
            "nombre": "Nombre del producto",
            "descripcion": "Descripción detallada",
            "categoria": "Categoría",
            "precio": 99.99,
            "stock": 10,
            "ubicacion": "Almacén A",
            "proveedor": "Proveedor XYZ"
        }
    """
    data = request.json

    # Validar campos requeridos
    if not data or 'codigo' not in data or 'nombre' not in data:
        return jsonify({
            'success': False,
            'error': 'Faltan campos requeridos: codigo, nombre'
        }), 400

    conn = get_db()
    cur = conn.cursor()

    try:
        # Insertar producto
        cur.execute("""
            INSERT INTO productos
            (codigo, nombre, descripcion, categoria, precio, stock, ubicacion, proveedor)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) 
            RETURNING id
        """, (
            data['codigo'],
            data['nombre'],
            data.get('descripcion'),
            data.get('categoria'),
            data.get('precio'),
            data.get('stock', 0),
            data.get('ubicacion'),
            data.get('proveedor')
        ))

        producto_id = cur.fetchone()[0]

        logger.info(f"Producto creado: {data['codigo']} (ID: {producto_id})")

        # Generar texto optimizado para embedding
        texto = preparar_texto_embedding(data)
        logger.info(f"Texto para embedding: {texto[:100]}...")

        # Generar embedding
        embedding = generar_embedding(texto)

        if not embedding:
            # Rollback si falla el embedding
            conn.rollback()
            return jsonify({
                'success': False,
                'error': 'Error generando embedding para el producto'
            }), 500

        # Convertir embedding a formato PostgreSQL
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'

        # Guardar embedding
        cur.execute("""
            INSERT INTO producto_embeddings (producto_id, embedding, texto_embebido)
            VALUES (%s, %s::vector(384), %s)
        """, (producto_id, embedding_str, texto))

        conn.commit()

        logger.info(f"Embedding guardado para producto {producto_id}")

        return jsonify({
            'success': True,
            'producto_id': producto_id,
            'mensaje': 'Producto creado exitosamente con embedding'
        }), 201

    except psycopg2.IntegrityError as e:
        conn.rollback()
        logger.error(f"Error de integridad: {e}")
        return jsonify({
            'success': False,
            'error': 'Código de producto duplicado o error de integridad'
        }), 400
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creando producto: {e}")
        raise
    finally:
        cur.close()
        conn.close()


@app.route('/api/productos/<int:producto_id>', methods=['GET'])
@handle_errors
def obtener_producto(producto_id):
    """
    Obtener detalles de un producto específico

    Args:
        producto_id: ID del producto

    Response:
        {
            "success": true,
            "producto": {...},
            "tiene_embedding": true
        }
    """
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT p.*, 
               pe.id IS NOT NULL as tiene_embedding,
               pe.fecha_generacion as embedding_fecha
        FROM productos p
        LEFT JOIN producto_embeddings pe ON p.id = pe.producto_id
        WHERE p.id = %s
    """, (producto_id,))

    producto = cur.fetchone()
    cur.close()
    conn.close()

    if not producto:
        return jsonify({
            'success': False,
            'error': 'Producto no encontrado'
        }), 404

    return jsonify({
        'success': True,
        'producto': dict(producto)
    })


@app.route('/api/productos/<int:producto_id>', methods=['PUT'])
@handle_errors
def actualizar_producto(producto_id):
    """
    Actualizar producto y regenerar su embedding

    Args:
        producto_id: ID del producto

    Request JSON:
        {
            "nombre": "Nuevo nombre",
            "descripcion": "Nueva descripción",
            ...
        }
    """
    data = request.json

    if not data:
        return jsonify({
            'success': False,
            'error': 'No se proporcionaron datos para actualizar'
        }), 400

    conn = get_db()
    cur = conn.cursor()

    try:
        # Construir query de actualización dinámicamente
        campos_actualizar = []
        valores = []

        campos_permitidos = ['nombre', 'descripcion', 'categoria', 'precio',
                            'stock', 'ubicacion', 'proveedor', 'activo']

        for campo in campos_permitidos:
            if campo in data:
                campos_actualizar.append(f"{campo} = %s")
                valores.append(data[campo])

        if not campos_actualizar:
            return jsonify({
                'success': False,
                'error': 'No se proporcionaron campos válidos para actualizar'
            }), 400

        # Agregar fecha de actualización
        campos_actualizar.append("fecha_actualizacion = CURRENT_TIMESTAMP")
        valores.append(producto_id)

        # Actualizar producto
        query = f"""
            UPDATE productos 
            SET {', '.join(campos_actualizar)}
            WHERE id = %s
            RETURNING codigo, nombre, descripcion, categoria, proveedor
        """

        cur.execute(query, valores)
        producto_actualizado = cur.fetchone()

        if not producto_actualizado:
            conn.rollback()
            return jsonify({
                'success': False,
                'error': 'Producto no encontrado'
            }), 404

        logger.info(f"Producto {producto_id} actualizado")

        # Regenerar embedding si cambiaron campos relevantes
        if any(campo in data for campo in ['nombre', 'descripcion', 'categoria', 'proveedor']):
            producto_dict = {
                'codigo': producto_actualizado[0],
                'nombre': producto_actualizado[1],
                'descripcion': producto_actualizado[2],
                'categoria': producto_actualizado[3],
                'proveedor': producto_actualizado[4]
            }

            texto = preparar_texto_embedding(producto_dict)
            embedding = generar_embedding(texto)

            if embedding:
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'

                # Actualizar o insertar embedding
                cur.execute("""
                    INSERT INTO producto_embeddings (producto_id, embedding, texto_embebido)
                    VALUES (%s, %s::vector(384), %s)
                    ON CONFLICT (producto_id) 
                    DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        texto_embebido = EXCLUDED.texto_embebido,
                        fecha_generacion = CURRENT_TIMESTAMP
                """, (producto_id, embedding_str, texto))

                logger.info(f"Embedding regenerado para producto {producto_id}")

        conn.commit()

        return jsonify({
            'success': True,
            'producto_id': producto_id,
            'mensaje': 'Producto actualizado exitosamente'
        })

    except Exception as e:
        conn.rollback()
        logger.error(f"Error actualizando producto: {e}")
        raise
    finally:
        cur.close()
        conn.close()


@app.route('/api/productos/<int:producto_id>', methods=['DELETE'])
@handle_errors
def eliminar_producto(producto_id):
    """
    Eliminar producto (soft delete - marca como inactivo)

    Args:
        producto_id: ID del producto
    """
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE productos 
            SET activo = false, fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING codigo
        """, (producto_id,))

        resultado = cur.fetchone()

        if not resultado:
            conn.rollback()
            return jsonify({
                'success': False,
                'error': 'Producto no encontrado'
            }), 404

        conn.commit()
        logger.info(f"Producto {producto_id} ({resultado[0]}) marcado como inactivo")

        return jsonify({
            'success': True,
            'mensaje': 'Producto eliminado exitosamente'
        })

    except Exception as e:
        conn.rollback()
        logger.error(f"Error eliminando producto: {e}")
        raise
    finally:
        cur.close()
        conn.close()


@app.route('/', methods=['GET'])
def home():
    """
    Documentación de la API
    """
    return jsonify({
        'api': 'Sistema de Inventario con Búsqueda Semántica',
        'version': '1.0.0',
        'endpoints': {
            'GET /': 'Esta documentación',
            'GET /health': 'Estado de servicios',
            'GET /api/productos': 'Listar productos (paginado)',
            'GET /api/productos/<id>': 'Obtener producto específico',
            'POST /api/productos': 'Crear nuevo producto',
            'PUT /api/productos/<id>': 'Actualizar producto',
            'DELETE /api/productos/<id>': 'Eliminar producto (soft delete)',
            'POST /api/productos/buscar': 'Búsqueda semántica',
            'GET /api/productos/sugerencias': 'Sugerencias para búsquedas'
        },
        'tips_busqueda': {
            'buenas_practicas': [
                'Incluir marcas: "Dell", "Logitech", "LG"',
                'Ser específico: "laptop" mejor que "computadora"',
                'Usar características: "inalámbrico", "RGB", "ergonómico"',
                'Incluir modelos: "XPS 13", "27 pulgadas"'
            ],
            'ejemplos': {
                'bueno': 'laptop Dell XPS notebook',
                'malo': 'computadora portátil'
            }
        },
        'modelo_embeddings': OLLAMA_MODEL,
        'dimensiones': 384
    })


@app.route('/api/productos/sugerencias', methods=['GET'])
def obtener_sugerencias():
    """
    Obtener sugerencias para mejorar búsquedas

    Response:
        {
            "sugerencias": [
                "laptop notebook Dell XPS",
                "mouse inalámbrico Logitech",
                ...
            ],
            "tips": [...]
        }
    """
    return jsonify({
        'success': True,
        'sugerencias': [
            'laptop notebook Dell XPS',
            'mouse inalámbrico Logitech wireless',
            'teclado mecánico RGB switches',
            'monitor pantalla LG 27 pulgadas 4K',
            'silla oficina ergonómica lumbar'
        ],
        'tips': [
            '✓ Incluye marcas específicas en tu búsqueda',
            '✓ Usa múltiples sinónimos: "laptop notebook"',
            '✓ Menciona características: "inalámbrico", "mecánico", "ergonómico"',
            '✓ Especifica tamaños y modelos: "27 pulgadas", "XPS 13"',
            '✗ Evita términos muy genéricos: "dispositivo", "cosa", "aparato"'
        ],
        'categorias_disponibles': [
            'Electrónica',
            'Accesorios',
            'Muebles'
        ]
    })


@app.route('/', methods=['GET'])
def health_check():
    """
    Verificar estado de servicios

    Response:
        {
            "status": "ok/degraded/error",
            "postgres": {"status": "ok", "detail": "..."},
            "ollama": {"status": "ok", "modelo": "all-minilm"}
        }
    """
    health_status = {
        'postgres': {'status': 'unknown'},
        'ollama': {'status': 'unknown'}
    }

    # Verificar PostgreSQL
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM productos")
        productos_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM producto_embeddings")
        embeddings_count = cur.fetchone()[0]
        cur.close()
        conn.close()

        health_status['postgres'] = {
            'status': 'ok',
            'productos': productos_count,
            'embeddings': embeddings_count
        }
    except Exception as e:
        logger.error(f"Error en health check PostgreSQL: {e}")
        health_status['postgres'] = {
            'status': 'error',
            'error': str(e)
        }

    # Verificar Ollama
    try:
        models = ollama_client.list()
        model_names = [m.get('name', m.get('model', '')) for m in models.get('models', [])]
        model_disponible = any(OLLAMA_MODEL in name for name in model_names)

        health_status['ollama'] = {
            'status': 'ok' if model_disponible else 'warning',
            'modelo_configurado': OLLAMA_MODEL,
            'modelo_disponible': model_disponible,
            'modelos_instalados': len(model_names)
        }
    except Exception as e:
        logger.error(f"Error en health check Ollama: {e}")
        health_status['ollama'] = {
            'status': 'error',
            'error': str(e)
        }

    # Determinar estado general
    if all(s['status'] == 'ok' for s in health_status.values()):
        overall_status = 'ok'
        status_code = 200
    elif any(s['status'] == 'error' for s in health_status.values()):
        overall_status = 'error'
        status_code = 503
    else:
        overall_status = 'degraded'
        status_code = 200

    return jsonify({
        'status': overall_status,
        **health_status
    }), status_code


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5100, debug=True)