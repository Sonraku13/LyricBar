import os
import sys

# Ensure working directory is project root
project_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_dir)
sys.path.insert(0, project_dir)

# Prevent crash under pythonw.exe on Windows where stdout/stderr are None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from LyricBar.ui.ui import main

if __name__ == "__main__":
    main()
