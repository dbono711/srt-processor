# SRT Processor Development Makefile

.PHONY: dev build run stop clean logs shell test

# Development with hot reload
dev:
	docker-compose -f docker-compose.dev.yml up -d

# Build production image
build:
	docker build -t srt-processor .

# Run production container
run:
	docker run -d --name srt-processor -p 8501:8501 -p 9000-9100:9000-9100/udp --cap-add=NET_ADMIN srt-processor

# Stop and remove containers
stop:
	docker-compose -f docker-compose.dev.yml down
	docker stop srt-processor 2>/dev/null || true
	docker rm srt-processor 2>/dev/null || true

# Clean up images and containers
clean: stop
	docker-compose -f docker-compose.dev.yml down --rmi all --volumes
	docker rmi srt-processor 2>/dev/null || true

# View logs
logs:
	docker-compose -f docker-compose.dev.yml logs -f

# Shell into running container
shell:
	docker-compose -f docker-compose.dev.yml exec srt-processor-dev bash

# Run tests (if you add them later)
test:
	docker-compose -f docker-compose.dev.yml exec srt-processor-dev python -m pytest

# Help
help:
	@echo "Available commands:"
	@echo "  dev    - Start development environment with hot reload"
	@echo "  build  - Build production Docker image"
	@echo "  run    - Run production container"
	@echo "  stop   - Stop all containers"
	@echo "  clean  - Clean up containers and images"
	@echo "  logs   - View container logs"
	@echo "  shell  - Open shell in development container"
	@echo "  test   - Run tests"
