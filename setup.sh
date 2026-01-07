#!/bin/bash
# setup.sh

echo "=== Configurando Sistema de Inventario con Embeddings ==="

# 1. Crear directorios necesarios
mkdir -p data/postgres
mkdir -p data/ollama

# 2. Verificar que docker-compose.yml e init-db.sql existen
if [ ! -f "docker-compose.yml" ]; then
    echo "Error: docker compose.yml no encontrado"
    exit 1
fi

if [ ! -f "init-db.sql" ]; then
    echo "Error: init-db.sql no encontrado"
    exit 1
fi

# 3. Levantar servicios
echo "Iniciando servicios Docker..."
docker compose up -d

# 4. Esperar a que PostgreSQL esté listo
echo "Esperando a que PostgreSQL esté listo..."
sleep 15

# 5. Descargar modelo de embeddings en Ollama
echo "Descargando modelo all-minilm en Ollama..."
docker exec inventory_ollama ollama pull all-minilm

# 6. Verificar que el modelo se descargó
echo "Verificando modelo..."
docker exec inventory_ollama ollama list

# 7. Instalar dependencias Python (si no están instaladas)
echo "Instalando dependencias Python..."
pip install psycopg2-binary ollama

# 8. Generar embeddings iniciales
echo "Generando embeddings para productos..."
python3 generate_embeddings.py

echo ""
echo "=== ¡Configuración completada! ==="
echo ""
echo "Servicios disponibles:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Ollama: localhost:11434"
echo ""
echo "Comandos útiles:"
echo "  docker compose ps              # Ver estado de servicios"
echo "  docker compose logs -f         # Ver logs"
echo "  docker compose down            # Detener servicios"
echo "  docker compose down -v         # Detener y eliminar volúmenes"
echo ""
echo "Base de datos:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: inventario"
echo "  User: inventory_user"
echo "  Password: changeme_secure_password"