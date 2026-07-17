"""Punto de entrada de la interfaz web: python -m web.main"""

import importlib.util
import logging


def _check_dependencies() -> None:
    if importlib.util.find_spec("flask") is None:
        raise SystemExit(
            "Falta el paquete flask.\n"
            "Instálalo con:  pip install -r requirements.txt"
        )


def main() -> None:
    _check_dependencies()
    from bot import config
    from web.app import create_app

    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, threaded=True)


if __name__ == "__main__":
    main()
