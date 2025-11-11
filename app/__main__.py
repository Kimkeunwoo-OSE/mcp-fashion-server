from __future__ import annotations

import sys

if __name__ == "__main__":
    if "--desktop" in sys.argv:
        from .desktop import main as desktop_main

        desktop_main()
    elif "--ui" in sys.argv:
        from .main import run_ui_mode

        raise SystemExit(run_ui_mode())
    else:
        from .main import main

        raise SystemExit(main())
