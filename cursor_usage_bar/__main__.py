import sys


def check() -> int:
    from . import core

    try:
        usage = core.fetch_usage()
    except core.UsageError as exc:
        print(f"Erro: {exc}")
        return 1
    print("\n".join(core.detail_lines(usage)))
    return 0


def main():
    if "--check" in sys.argv:
        sys.exit(check())
    if sys.platform == "darwin":
        from .mac_app import run
    elif sys.platform == "win32":
        from .windows_app import run
    else:
        sys.exit("Plataforma não suportada: use macOS ou Windows")
    run()


if __name__ == "__main__":
    main()
