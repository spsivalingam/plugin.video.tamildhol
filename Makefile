ADDON_ID := plugin.video.tamildhol

.PHONY: up down restart logs logs-all shell check launch zip clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start Kodi in Docker (Web UI at http://localhost:8080)
	docker compose up -d
	@echo ""
	@echo "  ✅ Kodi is starting..."
	@echo "  🌐 Open http://localhost:8080 to access the Chorus2 Web UI"
	@echo "  📋 Run 'make logs' in another terminal to watch addon logs"
	@echo ""

down: ## Stop Kodi container
	docker compose down

restart: ## Restart container to reload code changes
	docker compose restart
	@echo "  🔄 Restarted. Refresh http://localhost:8000"

logs: ## Tail Kodi logs filtered to addon output
	docker exec kodi-tamildhol tail -f /config/.kodi/temp/kodi.log 2>/dev/null | grep -i --color=always "tamildhol\|error\|exception\|traceback"

logs-all: ## Tail full Kodi logs
	docker exec kodi-tamildhol tail -f /config/.kodi/temp/kodi.log

shell: ## Open a shell inside the Kodi container
	docker compose exec kodi /bin/bash

check: ## Validate addon with kodi-addon-checker
	@command -v kodi-addon-checker >/dev/null 2>&1 || pip install -q kodi-addon-checker
	kodi-addon-checker .

launch: ## Launch the addon via JSON-RPC
	@curl -sf -X POST http://localhost:8080/jsonrpc \
	  -H "Content-Type: application/json" \
	  -d '{"jsonrpc":"2.0","method":"Addons.ExecuteAddon","params":{"addonid":"$(ADDON_ID)"},"id":1}' \
	  && echo "  ✅ Addon launched" \
	  || echo "  ❌ Failed — is Kodi running? (make up)"

zip: ## Package addon as an installable zip
	cd .. && zip -r $(ADDON_ID).zip $(ADDON_ID)/ \
	  -x "*.pyc" "*__pycache__*" "*.git*" "*docker-compose*" "*Makefile" "*kodi_data*"
	@echo "  📦 Created ../$(ADDON_ID).zip"

clean: ## Remove all Docker data (full reset)
	docker compose down -v
	@echo "  🧹 Cleaned up all containers and volumes"
