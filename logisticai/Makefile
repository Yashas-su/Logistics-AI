.PHONY: all infra-up infra-down infra-status seed run-optimizer run-inference run-ingestion run-ws-hub run-frontend test load-test docker-build docker-push k8s-deploy clean

# ── Infrastructure ────────────────────────────────────────────────────────
infra-up:
	@echo "Starting infrastructure (Redis, Kafka, Postgres, Prometheus, Grafana)..."
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@docker compose ps

infra-down:
	docker compose down -v

infra-status:
	docker compose ps

# ── Data ─────────────────────────────────────────────────────────────────
seed:
	@echo "Seeding demo shipment data..."
	cd scripts && pip install -q -r ../services/optimizer/requirements.txt && python seed_demo_data.py

# ── Services ─────────────────────────────────────────────────────────────
run-optimizer:
	@echo "Starting Optimizer Service on :8001..."
	cd services/optimizer && \
		pip install -q -r requirements.txt && \
		uvicorn main:app --host 0.0.0.0 --port 8001 --reload

run-inference:
	@echo "Starting Inference Service on :8002..."
	cd services/inference && \
		pip install -q -r requirements.txt && \
		uvicorn main:app --host 0.0.0.0 --port 8002 --reload

run-ingestion:
	@echo "Starting GPS Ingestion + Stream Simulator..."
	cd services/ingestion && \
		pip install -q -r requirements.txt && \
		python main.py

run-ws-hub:
	@echo "Starting WebSocket Hub on :8080..."
	cd services/websocket-hub && \
		go mod tidy && \
		go run main.go

run-frontend:
	@echo "Starting React dashboard on :5173..."
	cd frontend && \
		npm install && \
		npm run dev

run-all:
	@echo "Starting all services (requires tmux)..."
	tmux new-session -d -s logisticai \; \
		send-keys 'make run-optimizer' C-m \; \
		split-window -h \; send-keys 'make run-inference' C-m \; \
		split-window -v \; send-keys 'make run-ingestion' C-m \; \
		new-window \; send-keys 'make run-ws-hub' C-m \; \
		split-window -h \; send-keys 'make run-frontend' C-m \; \
		attach

# ── Tests ────────────────────────────────────────────────────────────────
test:
	@echo "Running integration tests..."
	cd tests && pip install -q pytest pytest-asyncio httpx && \
		pytest integration/ -v --asyncio-mode=auto

test-unit:
	cd services/optimizer && pip install -q -r requirements.txt pytest && pytest tests/ -v

load-test:
	@which k6 > /dev/null || (echo "Install k6: https://k6.io/docs/get-started/installation/" && exit 1)
	k6 run tests/load/optimizer_load_test.js \
		-e API_BASE=http://localhost:8001 \
		-e JWT_TOKEN=$$(python scripts/gen_test_jwt.py)

# ── ML Training (local demo) ─────────────────────────────────────────────
train-demo:
	@echo "Training demo XGBoost model on synthetic data..."
	cd ml && pip install -q -r requirements.txt && python train_delay_model.py --demo

# ── Docker ───────────────────────────────────────────────────────────────
docker-build:
	docker build -t logisticai/optimizer:latest services/optimizer/
	docker build -t logisticai/inference:latest services/inference/
	docker build -t logisticai/ingestion:latest services/ingestion/
	docker build -t logisticai/ws-hub:latest    services/websocket-hub/

docker-push:
	docker tag logisticai/optimizer:latest gcr.io/$(PROJECT_ID)/optimizer:latest
	docker tag logisticai/inference:latest gcr.io/$(PROJECT_ID)/inference:latest
	docker push gcr.io/$(PROJECT_ID)/optimizer:latest
	docker push gcr.io/$(PROJECT_ID)/inference:latest

# ── Kubernetes ───────────────────────────────────────────────────────────
k8s-deploy:
	kubectl apply -f k8s/
	kubectl rollout status deployment/optimizer-service -n logistics
	kubectl rollout status deployment/inference-service -n logistics

# ── Terraform ────────────────────────────────────────────────────────────
tf-init:
	cd terraform && terraform init

tf-plan:
	cd terraform && terraform plan -var="project_id=$(PROJECT_ID)"

tf-apply:
	cd terraform && terraform apply -var="project_id=$(PROJECT_ID)" -auto-approve

# ── Utilities ────────────────────────────────────────────────────────────
health:
	bash scripts/health_check.sh

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	docker compose down -v 2>/dev/null || true
