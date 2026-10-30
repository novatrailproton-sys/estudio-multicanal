from __future__ import annotations

import argparse
import socket
import threading
import webbrowser


def main():
    parser = argparse.ArgumentParser(description="Estudio Multicanal")
    parser.add_argument("--port", type=int, default=57321)
    parser.add_argument("--data", default=None)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    import uvicorn
    from .server import create_app
    with socket.socket() as check:
        check.settimeout(.3)
        if check.connect_ex(("127.0.0.1", args.port)) == 0:
            print(f"El puerto {args.port} ya está ocupado. Abre el estudio existente o usa --port.")
            if not args.no_browser:
                webbrowser.open(f"http://127.0.0.1:{args.port}")
            return
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()
    print("Estudio Multicanal — http://127.0.0.1:"+str(args.port))
    print("Cierra esta ventana para detenerlo. Los proyectos y la cola se conservan.")
    uvicorn.run(create_app(args.data), host="127.0.0.1", port=args.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
