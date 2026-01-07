# 🗄️ Sistema de Inventario con Búsqueda Semántica

Sistema de gestión de inventario con capacidades de búsqueda semántica usando embeddings generados con Ollama y almacenados en PostgreSQL con pgvector.

## 📋 Requisitos

- Docker y Docker Compose
- Python 3.8+
- make
- 6GB RAM mínimo
- 10GB espacio en disco

## 🚀 Inicio Rápido

```bash
# 1. Clonar proyecto
git clone <tu-repositorio>
cd ollama-inventario

# 2. Desplegar todo
make deploy

# 3. Generar embeddings
make embeddings

# 4. Ver ayuda
make help
```

El comando `make deploy` hace todo automáticamente:
- ✅ Verifica requisitos (Docker, Python)
- ✅ Crea entorno virtual Python
- ✅ Instala dependencias
- ✅ Configura variables de entorno
- ✅ Inicia PostgreSQL + Ollama
- ✅ Descarga modelo de embeddings

## 📋 Comandos Principales

| Comando | Descripción |
|---------|-------------|
| `make help` | Ver todos los comandos |
| `make deploy` | Despliegue completo |
| `make start` | Iniciar servicios |
| `make stop` | Detener servicios |
| `make restart` | Reiniciar servicios |
| `make status` | Ver estado |
| `make logs` | Ver logs en tiempo real |
| `make embeddings` | Generar embeddings |
| `make backup` | Crear backup de BD |
| `make test` | Ejecutar pruebas |
| `make clean` | Limpiar temporales |

Ver más comandos: `make help`

## 🔧 Configuración

### Variables de Entorno

Crea `.env` desde `.env.example`:
```bash
make config
nano .env
```

Edita las credenciales:
```bash
DB_PASSWORD=tu_password_segura
OLLAMA_HOST=http://localhost:11434
```

### Cambiar Contraseña de PostgreSQL

Edita `docker-compose.yml`:
```yaml
POSTGRES_PASSWORD: tu_password_segura
```

⚠️ **Importante**: Cambia las contraseñas antes de usar en producción.

## 💻 Uso del Sistema

```bash
# Generar embeddings
make embeddings

# Ver estado de servicios
make status

# Acceder a PostgreSQL
make db-shell

# Hacer backup
make backup

# Restaurar backup
make restore FILE=backups/archivo.sql.gz
```

## 🗄️ Base de Datos

### Acceder a PostgreSQL
```bash
make db-shell
```

### Consultas SQL Útiles
```sql
-- Ver todos los productos
SELECT * FROM productos;

-- Ver productos con embeddings
SELECT p.*, pe.fecha_generacion 
FROM productos p 
JOIN producto_embeddings pe ON p.id = pe.producto_id;
```

### Backup y Restore
```bash
make backup                           # Crear backup
make list-backups                     # Ver backups
make restore FILE=backups/archivo.gz  # Restaurar
```

## 🔄 Uso Diario

```bash
# Ver estado
make status

# Ver logs
make logs

# Generar embeddings
make embeddings

# Hacer backup
make backup

# Reiniciar servicios
make restart
```

## 🌐 Despliegue en Servidor

```bash
# 1. Instalar Docker
curl -fsSL https://get.docker.com | sh

# 2. Instalar Docker Compose plugin
sudo apt-get update && sudo apt-get install docker-compose-plugin

# 3. Clonar y desplegar
git clone <tu-repo>
cd ollama-inventario
make deploy
```

### Seguridad

⚠️ **Antes de producción:**
1. Cambiar contraseñas en `docker-compose.yml` y `.env`
2. NO exponer PostgreSQL a Internet
3. Configurar firewall: `sudo ufw enable`
4. Configurar backups automáticos (ver abajo)

### Backup Automático (Cron)

```bash
crontab -e
# Agregar: backup diario a las 2 AM
0 2 * * * cd /ruta/a/ollama-inventario && make backup
```

## 🐛 Solución de Problemas

```bash
# Verificar requisitos
make check

# Ver estado de servicios
make status

# Ver logs de errores
make logs

# Ejecutar pruebas
make test

# Reiniciar todo
make restart

# Si hay problemas serios
make stop
make clean
make deploy
```

### Problemas Comunes

| Problema | Solución |
|----------|----------|
| PostgreSQL no inicia | `make logs-db` ver errores |
| Ollama no responde | `make restart` |
| Error de conexión | `make check` verificar requisitos |
| Poco espacio | `make clean && docker system prune` |

## 📁 Estructura del Proyecto

```
ollama-inventario/
├── Makefile                # Comandos simplificados
├── docker-compose.yml      # Servicios Docker
├── init-db.sql            # Inicialización de BD
├── generate_embeddings.py  # Script principal
├── requirements.txt       # Dependencias Python
├── .env.example           # Template de config
└── README.md              # Esta documentación
```

## 🔐 Servicios

- **PostgreSQL**: localhost:5432
- **Ollama API**: localhost:11434
- **Modelo**: all-minilm (vectores 384 dimensiones)

## 📦 Librerías Python

```txt
psycopg2-binary==2.9.9    # PostgreSQL
ollama==0.1.6             # Cliente Ollama
python-dotenv==1.0.0      # Variables de entorno
```

## 🎯 Características

- ✅ Búsqueda semántica con embeddings
- ✅ PostgreSQL con extensión pgvector
- ✅ Modelo all-minilm para embeddings
- ✅ Búsqueda por similitud de coseno
- ✅ Backups automáticos
- ✅ Docker Compose para fácil despliegue
- ✅ Makefile con 30+ comandos útiles

## 📚 Recursos

- [Documentación Ollama](https://ollama.ai)
- [Documentación pgvector](https://github.com/pgvector/pgvector)
- [Docker Compose](https://docs.docker.com/compose/)

---

**¿Necesitas ayuda?** Ejecuta `make help` para ver todos los comandos disponibles.

