import os
import sys
import shutil
from dotenv import load_dotenv
import logging

import resources_rc
import PyQt5.QtWidgets as qt
from app.settings import Settings
from app.gui.main_window import TranslationApp

logging.basicConfig(format='[%(asctime)s][%(levelname).1s][%(name)s] %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

def load_dotenv_example():
    if not os.path.exists(".env") and os.path.exists(".env.example"):
        shutil.copy(".env.example", ".env")
        logger.info("No .env file found, copied from .env.example. Please fill in the required environment variables.")
    load_dotenv()
    logger.info("Environment variables loaded from .env file")

def main():
    load_dotenv_example()  # Load environment variables from .env file
    settings = Settings.load("settings.json")
    
    launch_args = sys.argv
    if (darkmode := int(settings.dark_mode)):
        # let the dark mode setting take effect on Win11's TitleBar
        launch_args += ['-platform', f'windows:darkmode={darkmode}'] 
    app = qt.QApplication(launch_args)
    translator = TranslationApp(settings)
    translator.show()
    app.exec_()
    
if __name__ == "__main__":
    main()