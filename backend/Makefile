.PHONY: run test build up down clean install dev

# Default Python interpreter
PYTHON := python3

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Install development dependencies
	pip install -r requirements.txt
	pip install pytest httpx

run: ## Run development server with auto-reload
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

test: ## Run all tests
	pytest -v

test-coverage: ## Run tests with coverage
	pytest --cov=app --cov-report=html --cov-report=term-missing

lint: ## Run linting
	black --check .
	flake8 .

format: ## Format code
	black .
	isort .

build: ## Build Docker image
	docker build -t stylesync-segmentation:dev .

up: ## Run Docker container
	docker run --rm -p 8000:8000 --name stylesync-seg stylesync-segmentation:dev

down: ## Stop Docker container
	docker stop stylesync-seg || true

clean: ## Clean up Docker resources
	docker system prune -f
	docker image rm stylesync-segmentation:dev || true

smoke-test: ## Run smoke test against running service
	@echo "Testing health endpoint..."
	curl -s http://localhost:8000/healthz | jq .
	@echo "\nTesting StyleSync health endpoint..."
	curl -s http://localhost:8000/stylesync/healthz | jq .

smoke-test-segment: ## Run segmentation smoke test (requires test image)
	@echo "Running segmentation test..."
	@if [ -f "tests/assets/simple_garment.jpg" ]; then \
		curl -s -X POST "http://localhost:8000/stylesync/segment" \
			-F "file=@tests/assets/simple_garment.jpg" | jq '.mask_area_ratio, .engine, .fallback_used'; \
	else \
		echo "No test image found. Generate with: python tests/generate_test_images.py tests/assets"; \
	fi

generate-test-images: ## Generate synthetic test images
	$(PYTHON) tests/generate_test_images.py tests/assets

logs: ## View Docker container logs
	docker logs stylesync-seg

shell: ## Open shell in running container
	docker exec -it stylesync-seg /bin/bash

check-deps: ## Check if all dependencies are available
	@echo "Checking Python dependencies..."
	@$(PYTHON) -c "import fastapi, uvicorn, numpy, cv2, rembg, PIL, loguru; print('✓ All core dependencies available')" || echo "✗ Missing dependencies"

benchmark: ## Run basic performance benchmark
	@echo "Running performance benchmark..."
	@if [ -f "tests/assets/simple_garment.jpg" ]; then \
		echo "Testing 10 requests..."; \
		time for i in {1..10}; do \
			curl -s -X POST "http://localhost:8000/stylesync/segment" \
				-F "file=@tests/assets/simple_garment.jpg" > /dev/null; \
		done; \
	else \
		echo "No test image found. Run: make generate-test-images"; \
	fi

metrics: ## Get current metrics
	curl -s http://localhost:8000/stylesync/metrics | jq .
