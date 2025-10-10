# -------- Settings --------
DC            ?= docker compose
COMPOSE_FILE  ?= docker-compose.yml
PROJECT_NAME  ?= $(notdir $(CURDIR))

APP_SERVICE   ?= app
DB_SERVICE    ?= neo4j

# Pass extra args like: make up ARGS="--build"
ARGS          ?=

# -------- Phony targets --------
.PHONY: help build rebuild up down stop start restart ps logs logs-app logs-db \
        shell shell-app shell-db exec exec-app exec-db \
        bash-app bash-db cypher db-browser clean prune

# -------- Help --------
help:
	@echo "make build        - Build all services"
	@echo "make rebuild      - Rebuild without cache"
	@echo "make up           - Start in background"
	@echo "make down         - Stop and remove containers, networks"
	@echo "make ps           - List running services"
	@echo "make logs         - Tail all logs"
	@echo "make logs-app     - Tail app logs"
	@echo "make logs-db      - Tail neo4j logs"
	@echo "make shell-app    - /bin/sh into app"
	@echo "make bash-app     - /bin/bash into app"
	@echo "make shell-db     - /bin/sh into neo4j"
	@echo "make bash-db      - /bin/bash into neo4j"
	@echo "make venv         - Create virtualenv (if needed)"
	@echo "make test ARGS='--verbose' - Run tests in Docker"
	@echo "make test-local   - Run tests locally"
	@echo "make cypher       - Open cypher-shell (needs creds)"
	@echo "make db-browser   - Print Neo4j Browser URL"
	@echo "make clean        - Remove containers (keep volumes)"
	@echo "make prune        - Remove containers + volumes"

# -------- Compose wrappers --------
build:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) build $(ARGS)

rebuild:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) build --no-cache $(ARGS)

up:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) up -d $(ARGS)

down:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) down $(ARGS)

stop:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) stop

start:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) start

restart:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) restart

ps:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) ps

logs:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) logs -f

logs-app:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) logs -f $(APP_SERVICE)

logs-db:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) logs -f $(DB_SERVICE)

# -------- Exec / Shell helpers --------
shell-app:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) exec $(APP_SERVICE) /bin/sh

bash-app:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) exec $(APP_SERVICE) /bin/bash

shell-db:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) exec $(DB_SERVICE) /bin/sh

bash-db:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) exec $(DB_SERVICE) /bin/bash

# -------- Virtualenv helpers --------
venv:
	@echo "Creating virtualenv..."
	python3.12 -m venv .venv
	. .venv/bin/activate; python -m pip install -U pip; CMAKE_ARGS="-DGGML_CUDA=ON" python -m pip install -e .[test] --no-cache-dir; python -m spacy download en_core_web_sm


# -------- Unit Test Helpers --------
# Usage: make test ARGS="--verbose"
test-local:
	@echo "Running local tests..."
	.venv/bin/python -m unittest discover -s tests -p "*.py" -v

coverage:
	@echo "Running tests with coverage..."
	. .venv/bin/activate; coverage run -m unittest discover -s tests -p "*.py"
	.venv/bin/activate; coverage report -m

test:
	@echo "Running tests in Docker..."
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) run --rm $(APP_SERVICE) \
		python -m unittest discover -s tests -p "*.py" $(ARGS)

# Generic: make exec S=app C="env"
exec:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) exec $${S:?Set S=<service>} sh -lc $${C:?Set C='<command>'}

# Convenience aliases
exec-app:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) exec $(APP_SERVICE) sh -lc $${C:?Set C='<command>'}

exec-db:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) exec $(DB_SERVICE) sh -lc $${C:?Set C='<command>'}

# -------- Neo4j helpers --------
# Usage: make cypher C="MATCH (n) RETURN count(n);"
cypher:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) exec -e NEO4J_AUTH -T $(DB_SERVICE) \
		bash -lc "printf '%s\n' $${C:?Set C='<cypher query>'} | cypher-shell -u $${NEO4J_AUTH%%/*} -p $${NEO4J_AUTH##*/}"

db-browser:
	@echo "Open Neo4j Browser: http://localhost:7474  (bolt://localhost:7687)"

# -------- Cleanup --------
clean: down
	@echo "Containers removed (volumes kept)."

prune:
	$(DC) -p $(PROJECT_NAME) -f $(COMPOSE_FILE) down -v