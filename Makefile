.DEFAULT_GOAL := help

ACCENT  := $(shell tput -Txterm setaf 2)
RESET := $(shell tput init)


stand:  ## Запустить локальный стенд и получить в нем шелл
	@docker-compose run --rm -d skabenclient sh -c "tail -F /dev/random"

test:  ## Запустить тест переданный аргументом [tests=[test_00_test]]
	@docker-compose run --rm skabenclient sh -c pytest /app/skabenclient

lint:  ## Запустить линтер
	@docker-compose run --rm skabenclient sh -c /lint.sh

help:
	@echo "\nКоманды:\n"
	@grep -E '^[a-zA-Z.%_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%2s$(ACCENT)%-20s${RESET} %s\n", " ", $$1, $$2}'
	@echo ""
