# generate_embeddings.py
import psycopg2
import ollama
import time
from psycopg2.extras import execute_values

# Configuración
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'inventario',
    'user': 'inventory_user',
    'password': 'changeme_secure_password'
}

OLLAMA_MODEL = 'all-minilm'


def conectar_db():
    """Conectar a PostgreSQL"""
    return psycopg2.connect(**DB_CONFIG)


def generar_embedding(texto):
    """Generar embedding usando Ollama"""
    try:
        response = ollama.embed(
            model=OLLAMA_MODEL,
            input=texto
        )
        return response['embeddings'][0]
    except Exception as e:
        print(f"Error generando embedding: {e}")
        return None


def preparar_texto_producto(producto):
    """Preparar texto descriptivo del producto para embedding"""
    texto_parts = [
        f"Código: {producto['codigo']}",
        f"Nombre: {producto['nombre']}",
        f"Descripción: {producto['descripcion']}" if producto['descripcion'] else "",
        f"Categoría: {producto['categoria']}" if producto['categoria'] else "",
        f"Proveedor: {producto['proveedor']}" if producto['proveedor'] else ""
    ]
    return " ".join(filter(None, texto_parts))


def generar_embeddings_productos():
    """Generar embeddings para todos los productos sin embedding"""
    conn = conectar_db()
    cur = conn.cursor()

    try:
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
                cur.execute("""
                            INSERT INTO producto_embeddings (producto_id, embedding, texto_embebido)
                            VALUES (%s, %s, %s) ON CONFLICT (producto_id) 
                    DO
                            UPDATE SET
                                embedding = EXCLUDED.embedding,
                                texto_embebido = EXCLUDED.texto_embebido,
                                fecha_generacion = CURRENT_TIMESTAMP
                            """, (producto_dict['id'], embedding, texto))

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
            return

        # Buscar productos similares
        cur.execute("""
                    SELECT *
                    FROM buscar_productos_similares(%s::vector, %s)
                    """, (query_embedding, limite))

        resultados = cur.fetchall()

        print(f"\nResultados encontrados: {len(resultados)}")
        print("-" * 80)

        for i, resultado in enumerate(resultados, 1):
            producto_id, codigo, nombre, descripcion, similitud = resultado
            print(f"{i}. {codigo} - {nombre}")
            print(f"   Similitud: {similitud:.4f}")
            print(f"   Descripción: {descripcion[:100]}...")
            print()

    except Exception as e:
        print(f"Error en búsqueda: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    print("=== Sistema de Embeddings para Inventario ===\n")

    # Generar embeddings para productos existentes
    print("1. Generando embeddings para productos...")
    generar_embeddings_productos()

    # Ejemplos de búsqueda semántica
    print("\n2. Probando búsqueda semántica...\n")

    consultas_ejemplo = [
        "computadora portátil",
        "dispositivo para escribir",
        "pantalla grande",
        "mueble para sentarse"
    ]

    for consulta in consultas_ejemplo:
        buscar_productos_semanticamente(consulta, limite=3)
        print("=" * 80)