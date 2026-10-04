DATA    := data

.PHONY: help setup channels build up down logs shell check switch-ports rollback

help:
	@echo 'make setup     - first start on a clean data/: build, up, create channels'
	@echo 'make channels  - create channels + mumo map on the running server'
	@echo 'make build     - build the image'
	@echo 'make up        - start (64740 / Ice 6504)'
	@echo 'make logs      - follow the logs'
	@echo 'make check     - what is listening, and the channel count in the database'
	@echo 'make down      - stop'
	@echo 'make shell     - a shell inside the container'

setup:
	@scripts/initialsetup.sh

channels:
	@scripts/createchannel.sh

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

shell:
	docker compose exec prmurmur15 bash

check:
	@echo '--- listening ---'
	@ss -lntup 2>/dev/null | grep -E '64740|64741|6504|6505' || echo 'nothing on those ports'
	@echo '--- channels in the new database ---'
	@sqlite3 $(DATA)/murmur.sqlite 'select count(*) from channels;' 2>/dev/null || echo 'database not readable'
	@echo '--- containers ---'
	@docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'prmurmur' || true
