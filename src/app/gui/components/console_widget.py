import ast
import logging
from collections import deque
from typing import Callable, overload
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QLineEdit, QFrame
)
from PySide6.QtGui import QShortcut
from qt_extensions.core import TypedSignal

logger = logging.getLogger(__name__)


class CommandParseError(Exception):
    """Custom exception for command parsing errors."""
    pass

def parse_python_call(text: str):
    """Parse a string following Python's function call syntax.
    
    Returns:
        name (str): The function name.
        args (list): A list of positional arguments.
        kwargs (dict): A dictionary of keyword arguments.
    """
    node = ast.parse(text, mode="eval").body

    if not isinstance(node, ast.Call):
        raise CommandParseError("Expected a function call")
    if not isinstance(node.func, ast.Name):
        raise CommandParseError("Expected a simple function name")

    name = node.func.id
    try:
        args = [ast.literal_eval(arg) for arg in node.args]
        kwargs = {
            kw.arg: ast.literal_eval(kw.value)
            for kw in node.keywords if kw.arg is not None
        }
    except ValueError as e: 
        raise ValueError(f"Arguments can only be literals (strings, numbers, tuples, lists, dicts, booleans, and None). Error: {e}")
    return name, args, kwargs

class ConsoleWidget(QWidget):
    cmd_entered = TypedSignal(str)
    registry: dict[str, Callable] = {}
    history = deque(maxlen=20)
    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.logger = QPlainTextEdit()
        self.logger.setReadOnly(True)

        # Container styled like a QLineEdit
        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(6, 0, 6, 0)
        input_layout.setSpacing(4)

        self.line_edit_label = QLabel(">")
        self.line_edit = QLineEdit()
        self.line_edit.setFrame(False)

        input_layout.addWidget(self.line_edit_label)
        input_layout.addWidget(self.line_edit)
        main_layout.addWidget(self.logger)
        main_layout.addWidget(input_frame)

        self.line_edit.returnPressed.connect(self.on_return_pressed)
        self.cmd_entered.connect(self._call)
        
        self._cmd_history_idx = len(self.history)
        
        # Register default commands
        self._register(self._help, "help")
        self._register(self.clear, "clear")
        
        # Set up keyboard shortcuts for navigating command history
        self.prev_cmd_shortcut = QShortcut(Qt.Key.Key_Up, self)
        self.next_cmd_shortcut = QShortcut(Qt.Key.Key_Down, self)
        self.clear_cmd_shortcut = QShortcut(Qt.Key.Key_Escape, self)
        self.prev_cmd_shortcut.activated.connect(self._to_last_cmd)
        self.next_cmd_shortcut.activated.connect(self._to_next_cmd)
        self.clear_cmd_shortcut.activated.connect(self.line_edit.clear)
    
    def _help(self, cmd: str|None = None):
        """Display help information for registered commands."""
        if cmd is None:
            self.info("Available commands:\n" + "\n".join(f"- {name}" for name in self.registry.keys()))
        elif func := self.registry.get(cmd):
            doc = func.__doc__ or "No documentation available."
            self.info(f"Help on '{cmd}':\n{doc}")
        else:
            self.error(f"Unknown command: {cmd}.")
    
    def clear(self):
        """Clear the console output."""
        self.logger.clear()
        logger.debug("Console cleared.")
        
    def _to_last_cmd(self):
        self._cmd_history_idx = max(self._cmd_history_idx - 1, 0)
        if self._cmd_history_idx != -1 and self.history:
            self.line_edit.setText(self.history[self._cmd_history_idx])
            
    def _to_next_cmd(self):
        self._cmd_history_idx = min(self._cmd_history_idx + 1, len(self.history)-1)
        if self._cmd_history_idx != -1 and self.history:
            self.line_edit.setText(self.history[self._cmd_history_idx])  
        
    @overload
    def register(self, func: Callable, name: str | None = None) -> Callable: ...
    @overload
    def register(self, func: str) -> Callable[[Callable], Callable]: ...
    def register(self, func: Callable|str|None = None, name: str | None = None):
        if callable(func):
            return self._register(func, name)
        def decorator(func: Callable):
            return self._register(func, name)
        return decorator
    def _register(self, func: Callable, name: str | None = None):
        name = name or func.__name__
        if name in self.registry:
            logger.warning(f"Command '{name}' is already registered. Overwriting.")
        self.registry[name] = func
        return func
    
    def _call(self, command:str):
        """Call a registered function with the given command."""
        logger.debug(f"Executing command: {command}")
        try:
            func_name, args, kwargs = parse_python_call(command)
        except (SyntaxError, CommandParseError, ValueError) as e:
            e_name = type(e).__name__
            self.error(f'{e_name}: {e}')
            return
        
        if (func := self.registry.get(func_name)) is not None:
            try:
                if (res := func(*args, **kwargs)) is not None:
                    self.info(str(res))
            except Exception as e:
                self.error(f"Error occurred while executing command '{command}': {e}")
        else:
            self.error(f"Unknown command: {func_name}.")
        
    def info(self, text: str):
        self.logger.appendPlainText(text)
    def error(self, text: str):
        self.logger.appendHtml(f'<span style="color:red;">{text}</span>')
    def warning(self, text: str):
        self.logger.appendHtml(f'<span style="color:orange;">{text}</span>')
    def on_return_pressed(self):
        text = self.line_edit.text()
        self.history.append(text)
        self._cmd_history_idx = len(self.history) # Reset history index after a new command is entered
        self.info(f"> {text}")
        self.line_edit.clear()
        self.line_edit.setFocus()
        self.cmd_entered.emit(text)
            
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    
    # Use the console as a logger as well:
    class ConsoleLogger(logging.Handler):
        def __init__(self, console_widget: ConsoleWidget):
            super().__init__()
            self.console_widget = console_widget

        def emit(self, record):
            msg = self.format(record)
            self.console_widget.info(msg)
            
    app = QApplication(sys.argv)
    console_widget = ConsoleWidget()
    console_logger = ConsoleLogger(console_widget)
    
    @console_widget.register("foo1")
    def foo():
        """A simple test function that returns a string."""
        return "foo1 called"
    @console_widget.register
    def foo2(x):
        """A simple test function that takes an argument and returns a string."""
        return f"foo2 called with {x}"
    
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().addHandler(console_logger)
    formatter = logging.Formatter('[%(asctime)s][%(levelname)s][%(name)s] %(message)s')
    console_logger.setFormatter(formatter)
    
    console_widget.show()
    sys.exit(app.exec())