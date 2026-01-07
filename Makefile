# Makefile para Sistema de Inventario con Embeddings
# Uso: make [comando]

.PHONY: help install deploy start stop restart logs status clean backup restore test check

# Variables
PYTHON := python3
PIP := pip
VENV := .venv
DOCKER_COMPOSE := docker compose
POSTGRES_CONTAINER := inventory_postgres
OLLAMA_CONTAINER := inventory_ollama
BACKUP_DIR := backups

# Colores para output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Comando por defecto
help: ## Mostrar esta ayuda
	@echo "════════════════════════════════════════════════════"
	@echo "  Sistema de Inventario con Embeddings"
	@echo "════════════════════════════════════════════════════"
	@echo ""
	@echo "Comandos disponibles:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Uso: make [comando]"
	@echo ""

# ════════════════════════════════════════════════════════
# INSTALACIÓN Y CONFIGURACIÓN
# ════════════════════════════════════════════════════════

check: ## Verificar requisitos previos
	@echo "$(YELLOW)Verificando requisitos previos...$(NC)"
	@command -v docker >/dev/null 2>&1 || (echo "$(RED)✗ Docker no está instalado$(NC)" && exit 1)
	@command -v docker compose >/dev/null 2>&1 || (echo "$(RED)✗ Docker Compose no está instalado$(NC)" && exit 1)
	@command -v $(PYTHON) >/dev/null 2>&1 || (echo "$(RED)✗ Python 3 no está instalado$(NC)" && exit 1)
	@echo "$(GREEN)✓ Todos los requisitos están instalados$(NC)"

venv: ## Crear entorno virtual de Python
	@echo "$(YELLOW)Creando entorno virtual...$(NC)"
	@$(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)✓ Entorno virtual creado$(NC)"

install: venv ## Instalar dependencias de Python
	@echo "$(YELLOW)Instalando dependencias...$(NC)"
	@. $(VENV)/bin/activate && $(PIP) install --upgrade pip
	@. $(VENV)/bin/activate && $(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Dependencias instaladas$(NC)"

config: ## Crear archivo .env desde .env.example
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creando archivo .env...$(NC)"; \
		cp .env.example .env; \
		echo "$(YELLOW)⚠ IMPORTANTE: Edita .env y cambia las contraseñas$(NC)"; \
	else \
		echo "$(GREEN)✓ Archivo .env ya existe$(NC)"; \
	fi

setup: check config install ## Configuración inicial completa
	@echo "$(GREEN)✓ Configuración inicial completada$(NC)"

# ════════════════════════════════════════════════════════
# DOCKER - SERVICIOS
# ════════════════════════════════════════════════════════

build: ## Construir imágenes Docker
	@echo "$(YELLOW)Construyendo imágenes...$(NC)"
	@$(DOCKER_COMPOSE) build
	@echo "$(GREEN)✓ Imágenes construidas$(NC)"

start: ## Iniciar todos los servicios
	@echo "$(YELLOW)Iniciando servicios...$(NC)"
	@$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✓ Servicios iniciados$(NC)"
	@$(MAKE) --no-print-directory wait-db

stop: ## Detener todos los servicios
	@echo "$(YELLOW)Deteniendo servicios...$(NC)"
	@$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✓ Servicios detenidos$(NC)"

restart: ## Reiniciar todos los servicios
	@$(MAKE) --no-print-directory stop
	@$(MAKE) --no-print-directory start

logs: ## Ver logs de todos los servicios
	@$(DOCKER_COMPOSE) logs -f

logs-db: ## Ver logs de PostgreSQL
	@$(DOCKER_COMPOSE) logs -f postgres

logs-ollama: ## Ver logs de Ollama
	@$(DOCKER_COMPOSE) logs -f ollama

status: ## Ver estado de los servicios
	@echo "════════════════════════════════════════════════════"
	@echo "  Estado de Servicios"
	@echo "════════════════════════════════════════════════════"
	@$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "Uso de recursos:"
	@docker stats --no-stream $(POSTGRES_CONTAINER) $(OLLAMA_CONTAINER) 2>/dev/null || true

ps: status ## Alias de status

wait-db: ## Esperar a que PostgreSQL esté listo
	@echo "$(YELLOW)Esperando a PostgreSQL...$(NC)"
	@for i in $$(seq 1 30); do \
		if docker exec $(POSTGRES_CONTAINER) pg_isready -U inventory_user -d inventario >/dev/null 2>&1; then \
			echo "$(GREEN)✓ PostgreSQL está listo$(NC)"; \
			break; \
		fi; \
		echo -n "."; \
		sleep 2; \
	done

# ════════════════════════════════════════════════════════
# OLLAMA - MODELOS
# ════════════════════════════════════════════════════════

pull-model: ## Descargar modelo de embeddings (uso: make pull-model MODEL=nombre)
	@MODEL_NAME=$${MODEL:-all-minilm}; \
	echo "$(YELLOW)Descargando modelo $$MODEL_NAME...$(NC)"; \
	docker exec $(OLLAMA_CONTAINER) ollama pull $$MODEL_NAME && \
	echo "$(GREEN)✓ Modelo $$MODEL_NAME descargado$(NC)" || \
	echo "$(RED)✗ Error descargando modelo $$MODEL_NAME$(NC)"

list-models: ## Listar modelos instalados
	@echo "Modelos instalados en Ollama:"
	@docker exec $(OLLAMA_CONTAINER) ollama list

check-model: ## Verificar si un modelo está instalado (uso: make check-model MODEL=nombre)
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)Error: Especifica el modelo con MODEL=nombre$(NC)"; \
		echo "Ejemplo: make check-model MODEL=all-minilm"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Verificando modelo $(MODEL)...$(NC)"
	@if docker exec $(OLLAMA_CONTAINER) ollama list | grep -q "$(MODEL)"; then \
		echo "$(GREEN)✓ Modelo $(MODEL) está instalado$(NC)"; \
	else \
		echo "$(RED)✗ Modelo $(MODEL) NO está instalado$(NC)"; \
		exit 1; \
	fi

ensure-model: ## Asegurar que un modelo existe, descargarlo si no (uso: make ensure-model MODEL=nombre)
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)Error: Especifica el modelo con MODEL=nombre$(NC)"; \
		echo "Ejemplo: make ensure-model MODEL=all-minilm"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Verificando modelo $(MODEL)...$(NC)"
	@if docker exec $(OLLAMA_CONTAINER) ollama list | grep -q "$(MODEL)"; then \
		echo "$(GREEN)✓ Modelo $(MODEL) ya está instalado$(NC)"; \
	else \
		echo "$(YELLOW)Modelo $(MODEL) no encontrado, descargando...$(NC)"; \
		docker exec $(OLLAMA_CONTAINER) ollama pull $(MODEL) && \
		echo "$(GREEN)✓ Modelo $(MODEL) descargado e instalado$(NC)" || \
		(echo "$(RED)✗ Error descargando modelo $(MODEL)$(NC)" && exit 1); \
	fi

change-model: ensure-model ## Cambiar modelo de embeddings (uso: make change-model MODEL=nombre)
	@if [ -z "$(MODEL)" ]; then \
		echo "$(RED)Error: Especifica el modelo con MODEL=nombre$(NC)"; \
		echo ""; \
		echo "Modelos populares para embeddings:"; \
		echo "  • all-minilm (pequeño, rápido)"; \
		echo "  • nomic-embed-text (multilingüe, calidad alta)"; \
		echo "  • mxbai-embed-large (muy preciso)"; \
		echo ""; \
		echo "Ejemplo: make change-model MODEL=nomic-embed-text"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Cambiando modelo a $(MODEL)...$(NC)"
	@if [ -f .env ]; then \
		if grep -q "^OLLAMA_MODEL=" .env; then \
			sed -i.bak "s/^OLLAMA_MODEL=.*/OLLAMA_MODEL=$(MODEL)/" .env && rm -f .env.bak; \
		else \
			echo "OLLAMA_MODEL=$(MODEL)" >> .env; \
		fi; \
		echo "$(GREEN)✓ Modelo cambiado a $(MODEL) en .env$(NC)"; \
		echo ""; \
		echo "$(YELLOW)⚠️  IMPORTANTE:$(NC)"; \
		echo "  1. Reinicia los servicios: $(GREEN)make restart$(NC)"; \
		echo "  2. Regenera embeddings: $(GREEN)make embeddings$(NC)"; \
	else \
		echo "$(RED)✗ Error: Archivo .env no encontrado$(NC)"; \
		echo "Ejecuta: make config"; \
		exit 1; \
	fi

show-model: ## Mostrar modelo actual configurado
	@echo "Modelo configurado en .env:"
	@if [ -f .env ]; then \
		grep "^OLLAMA_MODEL=" .env || echo "$(YELLOW)⚠️  OLLAMA_MODEL no configurado$(NC)"; \
	else \
		echo "$(RED)✗ Archivo .env no encontrado$(NC)"; \
	fi
	@echo ""
	@echo "Modelos disponibles en Ollama:"
	@docker exec $(OLLAMA_CONTAINER) ollama list 2>/dev/null || echo "$(RED)✗ Ollama no está corriendo$(NC)"

# ════════════════════════════════════════════════════════
# BASE DE DATOS
# ════════════════════════════════════════════════════════

db-shell: ## Acceder a la consola de PostgreSQL
	@docker exec -it $(POSTGRES_CONTAINER) psql -U inventory_user -d inventario

db-reset: ## Reiniciar base de datos (¡CUIDADO! Elimina todos los datos)
	@echo "$(RED)⚠ ADVERTENCIA: Esto eliminará TODOS los datos$(NC)"
	@read -p "¿Estás seguro? (escribe 'si' para continuar): " confirm; \
	if [ "$$confirm" = "si" ]; then \
		echo "$(YELLOW)Reiniciando base de datos...$(NC)"; \
		$(MAKE) --no-print-directory stop; \
		docker volume rm ollama-inventario_postgres_data 2>/dev/null || true; \
		$(MAKE) --no-print-directory start; \
		echo "$(GREEN)✓ Base de datos reiniciada$(NC)"; \
	else \
		echo "Operación cancelada"; \
	fi

# ════════════════════════════════════════════════════════
# EMBEDDINGS
# ════════════════════════════════════════════════════════

embeddings: ## Generar embeddings para productos
	@echo "$(YELLOW)Generando embeddings...$(NC)"
	@. $(VENV)/bin/activate && $(PYTHON) generate_embeddings.py
	@echo "$(GREEN)✓ Embeddings generados$(NC)"

# ════════════════════════════════════════════════════════
# BACKUP Y RESTORE
# ════════════════════════════════════════════════════════

backup: ## Hacer backup de la base de datos
	@echo "$(YELLOW)Creando backup...$(NC)"
	@mkdir -p $(BACKUP_DIR)
	@TIMESTAMP=$$(date +"%Y%m%d_%H%M%S"); \
	BACKUP_FILE="$(BACKUP_DIR)/inventario_backup_$$TIMESTAMP.sql"; \
	docker exec $(POSTGRES_CONTAINER) pg_dump -U inventory_user inventario > $$BACKUP_FILE; \
	gzip $$BACKUP_FILE; \
	echo "$(GREEN)✓ Backup creado: $$BACKUP_FILE.gz$(NC)"; \
	du -h $$BACKUP_FILE.gz

restore: ## Restaurar backup (uso: make restore FILE=backups/archivo.sql.gz)
	@if [ -z "$(FILE)" ]; then \
		echo "$(RED)Error: Especifica el archivo con FILE=ruta/archivo.sql.gz$(NC)"; \
		echo "Backups disponibles:"; \
		ls -lh $(BACKUP_DIR)/ 2>/dev/null || echo "No hay backups"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restaurando desde $(FILE)...$(NC)"
	@echo "$(RED)⚠ ADVERTENCIA: Esto sobrescribirá los datos actuales$(NC)"
	@read -p "¿Continuar? (s/n): " confirm; \
	if [ "$$confirm" = "s" ] || [ "$$confirm" = "S" ]; then \
		gunzip -c $(FILE) | docker exec -i $(POSTGRES_CONTAINER) psql -U inventory_user inventario; \
		echo "$(GREEN)✓ Restauración completada$(NC)"; \
	else \
		echo "Operación cancelada"; \
	fi

list-backups: ## Listar backups disponibles
	@echo "Backups disponibles:"
	@ls -lh $(BACKUP_DIR)/ 2>/dev/null || echo "No hay backups"

clean-backups: ## Eliminar backups antiguos (más de 7 días)
	@echo "$(YELLOW)Eliminando backups antiguos...$(NC)"
	@find $(BACKUP_DIR) -name "*.gz" -type f -mtime +7 -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Backups antiguos eliminados$(NC)"

# ════════════════════════════════════════════════════════
# DESPLIEGUE COMPLETO
# ════════════════════════════════════════════════════════

deploy: check config setup start wait-db pull-model ## Despliegue completo automático
	@echo ""
	@echo "$(GREEN)════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)  ¡Despliegue completado exitosamente!$(NC)"
	@echo "$(GREEN)════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "Servicios disponibles:"
	@echo "  🗄️  PostgreSQL: localhost:5432"
	@echo "  🤖 Ollama API: localhost:11434"
	@echo ""
	@echo "Próximos pasos:"
	@echo "  1. Verifica el estado: $(GREEN)make status$(NC)"
	@echo "  2. Genera embeddings: $(GREEN)make embeddings$(NC)"
	@echo "  3. Ver logs: $(GREEN)make logs$(NC)"
	@echo ""
	@echo "$(YELLOW)⚠️  IMPORTANTE para producción:$(NC)"
	@echo "  - Cambia las contraseñas en .env y docker-compose.yml"
	@echo "  - Configura backups automáticos con cron"
	@echo "  - Configura el firewall del servidor"
	@echo ""

quick-start: deploy embeddings ## Inicio rápido (deploy + embeddings)
	@echo "$(GREEN)✓ Sistema listo para usar$(NC)"

# ════════════════════════════════════════════════════════
# LIMPIEZA
# ════════════════════════════════════════════════════════

clean: ## Limpiar archivos temporales
	@echo "$(YELLOW)Limpiando archivos temporales...$(NC)"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.log" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Limpieza completada$(NC)"

clean-all: stop clean ## Detener servicios y limpiar todo
	@echo "$(YELLOW)Limpiando todo...$(NC)"
	@rm -rf $(VENV) 2>/dev/null || true
	@echo "$(GREEN)✓ Limpieza completa$(NC)"

destroy: ## DESTRUIR todo (servicios + volúmenes + datos)
	@echo "$(RED)⚠ ADVERTENCIA: Esto eliminará TODOS los datos permanentemente$(NC)"
	@read -p "Escribe 'DESTRUIR' para continuar: " confirm; \
	if [ "$$confirm" = "DESTRUIR" ]; then \
		echo "$(YELLOW)Destruyendo todo...$(NC)"; \
		$(DOCKER_COMPOSE) down -v; \
		rm -rf $(VENV) data/ $(BACKUP_DIR)/ 2>/dev/null || true; \
		echo "$(GREEN)✓ Todo ha sido destruido$(NC)"; \
	else \
		echo "Operación cancelada"; \
	fi

# ════════════════════════════════════════════════════════
# DESARROLLO Y TESTING
# ════════════════════════════════════════════════════════

test: ## Ejecutar pruebas básicas
	@echo "$(YELLOW)Ejecutando pruebas...$(NC)"
	@echo "1. Verificando servicios..."
	@$(DOCKER_COMPOSE) ps
	@echo "2. Verificando PostgreSQL..."
	@docker exec $(POSTGRES_CONTAINER) pg_isready -U inventory_user
	@echo "3. Verificando Ollama..."
	@curl -s http://localhost:11434/api/tags > /dev/null && echo "$(GREEN)✓ Ollama OK$(NC)" || echo "$(RED)✗ Ollama ERROR$(NC)"
	@echo "4. Verificando Python..."
	@. $(VENV)/bin/activate && $(PYTHON) -c "import psycopg2, ollama; print('$(GREEN)✓ Python OK$(NC)')"
	@echo "$(GREEN)✓ Todas las pruebas pasaron$(NC)"

dev: start logs ## Modo desarrollo (start + logs)

shell: ## Abrir shell en el entorno virtual
	@. $(VENV)/bin/activate && exec $$SHELL

update: ## Actualizar imágenes Docker
	@echo "$(YELLOW)Actualizando imágenes...$(NC)"
	@$(DOCKER_COMPOSE) pull
	@$(MAKE) --no-print-directory restart
	@echo "$(GREEN)✓ Imágenes actualizadas$(NC)"

# ════════════════════════════════════════════════════════
# INFORMACIÓN
# ════════════════════════════════════════════════════════

info: ## Mostrar información del sistema
	@echo "════════════════════════════════════════════════════"
	@echo "  Información del Sistema"
	@echo "════════════════════════════════════════════════════"
	@echo ""
	@echo "Python: $$($(PYTHON) --version 2>&1)"
	@echo "Docker: $$(docker --version 2>&1)"
	@echo "Docker Compose: $$(docker compose version 2>&1)"
	@echo ""
	@echo "Archivos de configuración:"
	@echo "  .env: $$([ -f .env ] && echo '$(GREEN)✓$(NC)' || echo '$(RED)✗$(NC)')"
	@echo "  requirements.txt: $$([ -f requirements.txt ] && echo '$(GREEN)✓$(NC)' || echo '$(RED)✗$(NC)')"
	@echo "  docker-compose.yml: $$([ -f docker-compose.yml ] && echo '$(GREEN)✓$(NC)' || echo '$(RED)✗$(NC)')"
	@echo ""
	@echo "Entorno virtual: $$([ -d $(VENV) ] && echo '$(GREEN)✓$(NC)' || echo '$(RED)✗$(NC)')"
	@echo ""

