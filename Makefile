UV ?= uv
APP ?= kazumi
IOS_DEVICE ?= ios-primary
ARTIFACTS ?= artifacts
PYTEST_ARGS ?=

UV_RUN = env -u VIRTUAL_ENV $(UV) run
PYTEST = $(UV_RUN) pytest
RESULTS = $(ARTIFACTS)/allure-results
REPORT = $(ARTIFACTS)/allure-report

.PHONY: help setup lint format format-check unit quality collect smoke test android ios test-parallel report open-report clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "%-18s %s\n", $$1, $$2}'

setup: ## Sync the locked Python environment
	env -u VIRTUAL_ENV $(UV) sync

lint: ## Run Ruff lint checks
	$(UV_RUN) ruff check .

format: ## Format Python code with Ruff
	$(UV_RUN) ruff format .

format-check: ## Check Ruff formatting without changing files
	$(UV_RUN) ruff format --check .

unit: ## Run framework unit tests that do not require a device
	$(PYTEST) -q tests/unit

quality: lint format-check unit collect ## Run static checks, unit tests, and collect mobile tests

collect: ## Collect tests for APP (default: kazumi), without starting devices
	$(PYTEST) --collect-only --app-name $(APP)

smoke: ## Run non-destructive app launch checks on all configured platforms
	mkdir -p $(ARTIFACTS)
	$(PYTEST) tests/test_smoke.py --app-name $(APP) --alluredir=$(RESULTS) --clean-alluredir $(PYTEST_ARGS)

test: ## Run the full suite on all configured devices (first-launch cases clear app data)
	mkdir -p $(ARTIFACTS)
	$(PYTEST) --app-name $(APP) --alluredir=$(RESULTS) --clean-alluredir --junitxml=$(ARTIFACTS)/junit.xml $(PYTEST_ARGS)

android: ## Run the full suite on Android
	mkdir -p $(ARTIFACTS)
	$(PYTEST) --app-name $(APP) --platform android --alluredir=$(RESULTS) --clean-alluredir --junitxml=$(ARTIFACTS)/junit-android.xml $(PYTEST_ARGS)

ios: ## Run iOS on IOS_DEVICE (default: ios-primary real device)
	mkdir -p $(ARTIFACTS)
	$(PYTEST) --app-name $(APP) --platform ios --device $(IOS_DEVICE) --alluredir=$(RESULTS) --clean-alluredir --junitxml=$(ARTIFACTS)/junit-ios.xml $(PYTEST_ARGS)

test-parallel: ## Run the full suite with two xdist workers, grouped by app/device
	mkdir -p $(ARTIFACTS)
	$(PYTEST) -n 2 --dist loadgroup --app-name $(APP) --alluredir=$(RESULTS) --clean-alluredir --junitxml=$(ARTIFACTS)/junit-parallel.xml $(PYTEST_ARGS)

report: ## Generate the Allure HTML report from the latest run
	allure generate $(RESULTS) -o $(REPORT) --clean

open-report: ## Open the generated Allure report
	allure open $(REPORT)

clean: ## Remove generated test reports and artifacts
	rm -rf $(ARTIFACTS)

.PHONY: ios-simulator ios-all
ios-simulator: ## Run only the configured ios-simulator target
	$(MAKE) ios IOS_DEVICE=ios-simulator

ios-all: ## Run all configured iOS targets concurrently
	mkdir -p $(ARTIFACTS)
	$(PYTEST) -n 2 --dist loadgroup --app-name $(APP) --platform ios --alluredir=$(RESULTS) --clean-alluredir --junitxml=$(ARTIFACTS)/junit-parallel.xml $(PYTEST_ARGS)

.PHONY: integration
integration: ## Verify framework infrastructure (Docker required)
	$(PYTEST) tests/integration --run-integration $(PYTEST_ARGS)
