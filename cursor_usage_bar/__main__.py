import sys


def main():
    if sys.platform == "darwin":
        from .mac_app import run
    elif sys.platform == "win32":
        from .windows_app import run
    else:
        sys.exit("Plataforma não suportada: use macOS ou Windows")
    run()


if __name__ == "__main__":
    main()
