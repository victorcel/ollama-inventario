# generate_embeddings.py
import psycopg2
import ollama
import time
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'inventario'),
    'user': os.getenv('DB_USER', 'inventory_user'),
    'password': os.getenv('DB_PASSWORD', 'changeme_secure_password')
}

OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'all-minilm')
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')


def conectar_db():
    """Conectar a PostgreSQL"""
    return psycopg2.connect(**DB_CONFIG)


def generar_embedding(texto):
    """Generar embedding usando Ollama"""
    try:
        # Configurar cliente de Ollama si se especifica un host personalizado
        client = ollama.Client(host=OLLAMA_HOST)
        response = client.embed(
            model=OLLAMA_MODEL,
            input=texto
        )
        return response['embeddings'][0]
    except Exception as e:
        print(f"Error generando embedding: {e}")
        return None


def preparar_texto_producto(producto):
    """Preparar texto descriptivo del producto para embedding con énfasis semántico"""
    # Repetir información clave para aumentar el peso semántico
    nombre = producto['nombre']
    categoria = producto.get('categoria', '')
    descripcion = producto.get('descripcion', '')

    # Construir texto con repetición estratégica del nombre y categoría
    texto_parts = [
        f"{nombre}",  # Nombre al inicio (mayor peso)
        f"Producto: {nombre}",  # Repetir nombre
        f"Categoría: {categoria}" if categoria else "",
        f"Tipo: {categoria}" if categoria else "",  # Repetir categoría
        f"{descripcion}" if descripcion else "",
        f"Código: {producto['codigo']}",
        f"Proveedor: {producto['proveedor']}" if producto.get('proveedor') else ""
    ]
    return " ".join(filter(None, texto_parts))


def generar_embeddings_productos(forzar=False):
    """Generar embeddings para todos los productos sin embedding

    Args:
        forzar (bool): Si es True, regenera todos los embeddings aunque ya existan
    """
    conn = conectar_db()
    cur = conn.cursor()

    try:
        if forzar:
            print("FORZANDO regeneración de TODOS los embeddings...")
            # Eliminar todos los embeddings existentes
            cur.execute("DELETE FROM producto_embeddings")
            conn.commit()
            print(f"✓ Embeddings anteriores eliminados\n")

        # Obtener productos sin embedding
        cur.execute("""
                    SELECT p.id, p.codigo, p.nombre, p.descripcion, p.categoria, p.proveedor
                    FROM productos p
                             LEFT JOIN producto_embeddings pe ON p.id = pe.producto_id
                    WHERE pe.id IS NULL
                      AND p.activo = true
                    """)

        productos = cur.fetchall()
        print(f"Encontrados {len(productos)} productos sin embedding")

        for producto in productos:
            producto_dict = {
                'id': producto[0],
                'codigo': producto[1],
                'nombre': producto[2],
                'descripcion': producto[3],
                'categoria': producto[4],
                'proveedor': producto[5]
            }

            # Preparar texto
            texto = preparar_texto_producto(producto_dict)
            print(f"Generando embedding para: {producto_dict['codigo']} - {producto_dict['nombre']}")

            # Generar embedding
            embedding = generar_embedding(texto)

            if embedding:
                # Guardar en la base de datos
                # Convertir el embedding a formato string para PostgreSQL
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                cur.execute("""
                            INSERT INTO producto_embeddings (producto_id, embedding, texto_embebido)
                            VALUES (%s, %s, %s) ON CONFLICT (producto_id) 
                    DO
                            UPDATE SET
                                embedding = EXCLUDED.embedding,
                                texto_embebido = EXCLUDED.texto_embebido,
                                fecha_generacion = CURRENT_TIMESTAMP
                            """, (producto_dict['id'], embedding_str, texto))

                conn.commit()
                print(f"✓ Embedding guardado para producto {producto_dict['id']}")
            else:
                print(f"✗ Error generando embedding para producto {producto_dict['id']}")

            # Pequeña pausa para no sobrecargar
            time.sleep(0.5)

        print(f"\n✓ Proceso completado. {len(productos)} embeddings generados.")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def buscar_productos_semanticamente(consulta, limite=5):
    """Buscar productos usando búsqueda semántica"""
    conn = conectar_db()
    cur = conn.cursor()

    try:
        # Generar embedding de la consulta
        print(f"Buscando: '{consulta}'")
        query_embedding = generar_embedding(consulta)

        if not query_embedding:
            print("Error generando embedding de búsqueda")
            return []

        # Buscar productos similares
        # Convertir el embedding a formato string para PostgreSQL
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

        # NOTA: Hay un bug con ORDER BY + LIMIT en psycopg2 con pgvector
        # Solución: traer todos y limitar en Python
        cur.execute("""
                    SELECT 
                        p.id,
                        p.codigo,
                        p.nombre,
                        p.descripcion,
                        pe.embedding <=> %s::vector(384) as distancia
                    FROM producto_embeddings pe
                    JOIN productos p ON pe.producto_id = p.id
                    WHERE p.activo = true
                    ORDER BY 5
                    """, (embedding_str,))

        # Obtener todos los resultados y limitar en Python
        todos_resultados = cur.fetchall()
        # Calcular similitud (1 - distancia) y limitar
        resultados = [(r[0], r[1], r[2], r[3], 1 - r[4]) for r in todos_resultados[:limite]]

        print(f"\nResultados encontrados: {len(resultados)}")
        print("-" * 80)

        for i, resultado in enumerate(resultados, 1):
            producto_id, codigo, nombre, descripcion, similitud = resultado
            print(f"{i}. {codigo} - {nombre}")
            print(f"   Similitud: {similitud:.4f}")
            print(f"   Descripción: {descripcion[:100]}...")
            print()

        return resultados

    except Exception as e:
        print(f"Error en búsqueda: {e}")
        return []
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys

    print("=== Sistema de Embeddings para Inventario ===\n")

    # Verificar si se pasa --forzar como argumento
    forzar = '--forzar' in sys.argv or '-f' in sys.argv

    if forzar:
        print("⚠ MODO FORZADO: Regenerando TODOS los embeddings\n")

    # Generar embeddings para productos existentes
    print("1. Generando embeddings para productos...")
    generar_embeddings_productos(forzar=forzar)

    # Ejemplos de búsqueda semántica
    print("\n2. Probando búsqueda semántica...\n")

    consultas_ejemplo = [
        "laptop notebook Dell",
        "mouse inalámbrico Logitech",
        "teclado mecánico RGB",
        "monitor pantalla LG 27 pulgadas",
        "silla oficina ergonómica"
    ]

    for consulta in consultas_ejemplo:
        buscar_productos_semanticamente(consulta, limite=3)
        print("=" * 80)