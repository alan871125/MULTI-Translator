import os
import subprocess

print("Compiling Qt resources...")
subprocess.run(["pyside6-rcc", "src/resources.qrc", "-o", "src/resources_rc.py"])
print("Done!")