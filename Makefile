__VERSION__ = "1.9.3"

bump:
	bump2version --allow-dirty --current-version $(__VERSION__) patch Makefile custom_components/hitachi_yutaki/const.py custom_components/hitachi_yutaki/manifest.json

lint:
	ruff check custom_components --fix

install_dev:
	pip install -r requirements-dev.txt
