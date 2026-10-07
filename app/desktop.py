
from __future__ import annotations

import threading

import webview
from werkzeug.serving import make_server

from .api import app
from .voz import REFERENCIA_VOZ, preparar_dependencia_voz


HOST = "127.0.0.1"


def main() -> None:
    """Abre o servidor local e o exibe em uma janela nativa do Windows."""
    if REFERENCIA_VOZ.is_file():
        preparar_dependencia_voz()
    servidor = make_server(HOST, 0, app, threaded=True)
    porta = servidor.server_port
    thread = threading.Thread(target=servidor.serve_forever, daemon=True)
    thread.start()

    janela = webview.create_window(
        "G.U.Y.",
        f"http://{HOST}:{porta}",
        width=1280,
        height=820,
        min_size=(900, 600),
    )

    try:
        webview.start(gui="edgechromium")
    finally:
        servidor.shutdown()
        servidor.server_close()


if __name__ == "__main__":
    main()
