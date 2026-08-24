import os
import sys
import shutil
import traceback
import logging
import colorlog
from dotenv import load_dotenv
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QTextEdit

from app.models.filters import TableFilters
from app.models.session import TranslationSession
from app.presenter import TranslationAppPresenter
import resources_rc
from config import settings
from app.gui.main_window import TranslationApp

def setup_logging():
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s[%(asctime)s][%(levelname).1s][%(name)s]%(reset)s %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Remove any existing handlers (important if basicConfig() was called elsewhere)
    root.handlers.clear()

    root.addHandler(handler)
# Call once in main.py
setup_logging()

logger = logging.getLogger(__name__)

def load_dotenv_example():
    if not os.path.exists(".env") and os.path.exists(".env.example"):
        shutil.copy(".env.example", ".env")
        logger.info("No .env file found, copied from .env.example. Please fill in the required environment variables.")
    load_dotenv()
    logger.info("Environment variables loaded from .env file")

def exception_hook(exc_type, exc_value, exc_traceback):
    """
    Global function to catch unhandled exceptions and show them in a Qt Dialogue.
    """
    # Don't handle KeyboardInterrupt to allow Ctrl+C in terminal
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Format the traceback into a readable string
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = "".join(tb_lines)

    # Log to stderr so it still appears in the console/logs
    print(tb_text, file=sys.stderr)

    # Ensure a QApplication instance exists before making UI calls
    if QApplication.instance():
        # Create a critical error dialogue
        errorbox = QMessageBox()
        errorbox.setIcon(QMessageBox.Icon.Critical)
        errorbox.setWindowTitle("Error")
        errorbox.setText("An unhandled exception occurred.")
        errorbox.setInformativeText(str(exc_value))
        
        # Place full technical details inside an expandable text area
        details_box = QTextEdit()
        details_box.setPlainText(tb_text)
        details_box.setReadOnly(True)
        errorbox.setDetailedText(tb_text)
        
        errorbox.exec()
        
    # Optional: Exit the application after the dialogue closes
    # sys.exit(1)

# Assign the custom hook to the system interceptor
sys.excepthook = exception_hook

def main():
    load_dotenv_example()  # Load environment variables from .env file
    launch_args = sys.argv
    if (darkmode := int(settings.dark_mode)):
        # let the dark mode setting take effect on Win11's TitleBar
        launch_args += ['-platform', f'windows:darkmode={darkmode}'] 
    app = QApplication(launch_args)
    main_window = TranslationApp(settings)
    session = TranslationSession(settings)
    presenter = TranslationAppPresenter(main_window, settings, session=session, translation_tab_widget=main_window.translation_table)
    main_window.show()
    app.exec_()
    
if __name__ == "__main__":
    main()