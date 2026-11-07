"""Entry point SAP2SAFE.

Chạy GUI:  python main.py
Xem trợ giúp: python main.py --help
"""

import argparse
import sys

from sap2safe import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="SAP2SAFE",
        description=(
            "Chuyen 1 level SAP2000 sang SAFE qua file .F2K "
            "(ke ca load case nonlinear — dong bang vector phan luc)."
        ),
    )
    p.add_argument("--version", action="version", version=f"SAP2SAFE {__version__}")
    p.add_argument("--no-gui", action="store_true",
                   help="Chi kiem tra import, khong mo giao dien.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.no_gui:
        print(f"SAP2SAFE {__version__} — import OK (khong mo GUI).")
        return 0
    try:
        from sap2safe.app import run
    except ImportError as e:
        print(f"Khong mo duoc giao dien Tkinter: {e}", file=sys.stderr)
        print("Tren Windows: cai Python tu python.org (kem tcl/tk).", file=sys.stderr)
        return 1
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
