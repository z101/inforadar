# Makefile for the inforadar project

# Использовать bash для всех команд
SHELL := /bin/bash

# Определяем переменные для виртуального окружения
VENV_DIR = .venv
PYTHON = $(VENV_DIR)/bin/python
PIP = $(VENV_DIR)/bin/pip

# Цель по умолчанию, если просто вызвать 'make'
.DEFAULT_GOAL := help

# Используем .PHONY для целей, которые не являются файлами
.PHONY: help setup install test clean coverage debug-fetch debug-list debug-mark-read

help:
	@echo "Доступные команды:"
	@echo "  make setup          - Создать виртуальное окружение и установить зависимости для разработки."
	@echo "  make install        - Установить команду 'ir' глобально для текущего пользователя в WSL."
	@echo "  make test           - Запустить тесты внутри виртуального окружения."
	@echo "  make coverage       - Запустить тесты и показать отчет о покрытии кода."
	@echo ""
	@echo "Debug-режим (запуск из venv для отладки):"
	@echo "  make debug-fetch    - Запустить 'ir fetch' в режиме отладки."
	@echo "  make debug-list     - Запустить 'ir list --interactive' в режиме отладки."
	@echo "  make debug-mark-read - Запустить 'ir mark-read' в режиме отладки."
	@echo ""
	@echo "  make clean          - Удалить временные файлы и виртуальное окружение."

# Цель для настройки окружения разработки
setup: $(VENV_DIR)/touchfile

$(VENV_DIR)/touchfile: pyproject.toml
	@# Создаем venv, только если его еще нет
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo ">>> Создание виртуального окружения..."; \
		python3 -m venv $(VENV_DIR); \
	fi
	@echo ">>> Установка зависимостей в режиме редактирования..."
	@# Устанавливаем сам пакет и зависимости для тестов
	@$(PIP) install -e .
	@$(PIP) install pytest pytest-mock pytest-bdd
	@# Обновляем "флаг" успешной установки
	@touch $(VENV_DIR)/touchfile

# Цель для "глобальной" установки команды
install:
	@echo ">>> Установка команды 'ir' для текущего пользователя..."
	@echo "    Команда будет установлена в ~/.local/bin/"
	@echo "    Убедитесь, что директория ~/.local/bin добавлена в ваш системный PATH."
	@python3 -m pip install .
	@echo ">>> Установка завершена. Попробуйте открыть новый терминал и выполнить 'ir --help'."

# Цель для запуска тестов
test: setup
	@echo ">>> Запуск тестов..."
	@$(PYTHON) -m pytest

# Цель для отчета о покрытии
coverage: setup
	@echo ">>> Запуск тестов с отчетом о покрытии..."
	@$(PIP) install coverage
	@$(VENV_DIR)/bin/coverage run --source=src/inforadar -m pytest
	@echo ">>> Отчет о покрытии:"
	@$(VENV_DIR)/bin/coverage report -m --fail-under=70

# Debug-режим: запуск команд из venv для отладки
debug-fetch: setup
	@echo ">>> [DEBUG] Запуск ir fetch из venv..."
	@$(VENV_DIR)/bin/ir fetch

debug-list: setup
	@echo ">>> [DEBUG] Запуск ir list --interactive из venv..."
	@$(VENV_DIR)/bin/ir list --interactive

debug-mark-read: setup
	@echo ">>> [DEBUG] Запуск ir mark-read из venv..."
	@$(VENV_DIR)/bin/ir mark-read

# Цель для очистки проекта
clean:
	@echo ">>> Очистка проекта..."
	@rm -rf $(VENV_DIR)
	@rm -rf .pytest_cache .mypy_cache htmlcov .coverage
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name "*.egg-info" -exec rm -rf {} +