import os
import runpy


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OPS_SCRIPT = os.path.join(BASE_DIR, "ops", "backup_manual.py")


if __name__ == "__main__":
    runpy.run_path(OPS_SCRIPT, run_name="__main__")
