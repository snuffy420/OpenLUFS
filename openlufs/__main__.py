import sys

def main():
    if len(sys.argv)==3 and sys.argv[1]=="--diagnostics":
        from .diagnostics import run
        return run(sys.argv[2])
    if len(sys.argv)>1 and sys.argv[1] in {"analyze", "normalize", "--help", "-h"}:
        from .cli import main as cli_main
        return cli_main()
    from .gui import launch
    return launch()

if __name__=="__main__":
    raise SystemExit(main())
