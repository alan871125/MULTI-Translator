import os
import subprocess

print("Compiling Qt resources...")
subprocess.run(["pyrcc5", "src/resources.qrc", "-o", "src/resources_rc.py"])
print("Done!")