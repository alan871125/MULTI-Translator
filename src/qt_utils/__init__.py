import typing
from typing_extensions import ParamSpec
from PyQt5.QtCore import pyqtSignal

P = ParamSpec("P")
T1 = typing.TypeVar("T1")
T2 = typing.TypeVar("T2")
T3 = typing.TypeVar("T3")
T4 = typing.TypeVar("T4")
# You probably don't need more than 4 type variables for signals,
# Use a dataclass or any custom class to wrap multiple parameters for more complex signals if needed.
# T5 = TypeVar("T5")
# T6 = TypeVar("T6")

def _resolve_qt_type(t: typing.Any) -> type:
    """Map a typing construct to a real class pyqtSignal can accept."""
    if t is typing.Any:
        return object

    origin = typing.get_origin(t)

    if origin is typing.Literal:
        arg_types = {type(a) for a in typing.get_args(t)}
        return arg_types.pop() if len(arg_types) == 1 else object

    if origin is typing.Union:  # covers Optional[X] too
        args = [a for a in typing.get_args(t) if a is not type(None)]
        return _resolve_qt_type(args[0]) if len(args) == 1 else object

    if origin is not None:  # list[int], dict[str, int], etc.
        return origin

    if isinstance(t, type):
        return t

    return object  # last-resort fallback

class TypedQtSignal(typing.Generic[P]):
    @typing.overload
    def __new__(cls) -> "TypedQtSignal[[]]": ...
    @typing.overload
    def __new__(cls, t1: type[T1] | typing.Any, /) -> "TypedQtSignal[[T1]]": ...
    @typing.overload
    def __new__(cls, t1: type[T1] | typing.Any, t2: type[T2] | typing.Any, /) -> "TypedQtSignal[[T1, T2]]": ...
    @typing.overload
    def __new__(cls, t1: type[T1] | typing.Any, t2: type[T2] | typing.Any, t3: type[T3] | typing.Any, /) -> "TypedQtSignal[[T1, T2, T3]]": ...
    @typing.overload
    def __new__(cls, t1: type[T1] | typing.Any, t2: type[T2] | typing.Any, t3: type[T3] | typing.Any, t4: type[T4] | typing.Any, /) -> "TypedQtSignal[[T1, T2, T3, T4]]": ...
    def __new__(cls, *types: typing.Any) -> typing.Any:
        return typing.cast("TypedQtSignal[typing.Any]", super().__new__(cls))
    def __init__(self, *types: typing.Any) -> None:
        self._orig_types = types
        qt_types = tuple(_resolve_qt_type(t) for t in types)
        self._signal = pyqtSignal(*qt_types)

    @typing.overload
    def __get__(self, instance: None, owner: type) -> "TypedQtSignal[P]": ...
    @typing.overload
    def __get__(self, instance: object, owner: type) -> "_BoundTypedQtSignal[P]": ...
    def __get__(self, instance: object | None, owner: type) -> typing.Any:
        if instance is None:
            return self
        return _BoundTypedQtSignal(getattr(instance, self._attr_name))

    def __set_name__(self, owner: type, name: str) -> None:
        self._attr_name = f"_{name}_raw"
        setattr(owner, self._attr_name, self._signal)

class _BoundTypedQtSignal(typing.Generic[P]):
    def __init__(self, bound_signal: typing.Any) -> None:
        self._bound_signal = bound_signal

    def connect(self, slot: typing.Callable[P, typing.Any]) -> None:
        self._bound_signal.connect(slot)

    # This will cause a silence bug where the signal doesn't emit on a zero-arg signal, due to argument‑count mismatch.
    # def emit(self, *args: P.args, **kwargs: P.kwargs) -> None:
    #     self._bound_signal.emit(*args, **kwargs)
    @property
    def emit(self) -> typing.Callable[P, None]:
        # Return the *real* pyqtBoundSignal.emit, not a wrapping function.
        # This preserves Qt's native signal-to-signal connection semantics
        # (correct arity trimming) when this is used as a connect() target.
        return typing.cast(typing.Callable[P, None], self._bound_signal.emit)

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
    import sys
    class OtherWidget(QWidget):
        SignalType = TypedQtSignal[[int, str]]
        signal = TypedQtSignal(int, str)
    other_widget = OtherWidget()
    class MyWidget(QWidget):
        my_signal = TypedQtSignal(int, str)

        def __init__(self):
            super().__init__()
            self.my_signal.connect(self.handle_signal)
            # this should show warning in pylance if uncommented:
            # self.my_signal.connect(self.handle_signal_wrong)
            layout = QVBoxLayout()
            button = QPushButton("Emit Signal")
            button.clicked.connect(self.emit_signal)
            layout.addWidget(button)
            self.setLayout(layout)

        def emit_signal(self):
            self.my_signal.emit(42, "Hello")
        def handle_signal(self, number: int, text: str):
            print(f"Received signal with number: {number} and text: {text}")

        
        def handle_signal_wrong(self, number: str, text: int):
            ...
    app = QApplication(sys.argv)
    widget = MyWidget()
    widget.show()
    sys.exit(app.exec_())
    
    