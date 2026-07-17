SERVICES := vinu-news vinu-stock-price vinu-tools vinu-initial-analysis vinu-strategy vinu-simulator vinu-research

.PHONY: setup
setup:
	pip install --no-cache-dir -e ./vinu-lib
	@for svc in $(SERVICES); do \
		echo "installing $$svc..."; \
		pip install --no-cache-dir -e "./$$svc[dev]" || pip install --no-cache-dir -e "./$$svc"; \
	done
