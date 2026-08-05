SERVICES := vinu-news vinu-stock-price vinu-tools vinu-initial-analysis vinu-strategy vinu-simulator vinu-research vinu-portfolio vinu-live vinu-agent

.PHONY: setup
setup:
	pip install --no-cache-dir -e ./vinu-infra
	@for svc in $(SERVICES); do \
		echo "installing $$svc..."; \
		pip install --no-cache-dir -e "./$$svc[dev]" || pip install --no-cache-dir -e "./$$svc"; \
	done

.PHONY: models
models:
	pip install --no-cache-dir -e "./vinu-infra[models]"
	vinu-models --dir ./data/models

.PHONY: models-list
models-list:
	vinu-models --dir ./data/models --list
