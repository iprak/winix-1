HIDE ?= @
VENV ?= env
BIN_DIR ?= $(VENV)/bin/


prepare-venv:
	$(HIDE)python3.8 -m venv $(VENV)
	$(HIDE)$(BIN_DIR)easy_install pip
	$(HIDE)$(BIN_DIR)pip install --upgrade pip
	$(HIDE)$(BIN_DIR)pip install -c requirements.txt
	$(HIDE)$(BIN_DIR)pip install --editable .

fmt:
	$(HIDE)$(BIN_DIR)black winix

dist:
	$(HIDE)$(BIN_DIR)python setup.py sdist bdist_wheel
	$(HIDE)$(BIN_DIR)python3 -m twine upload  dist/*
