from typing import Callable, Iterable, Mapping, cast
from PyQt5.QtWidgets import QMainWindow, QMenu, QAction, QMenuBar

MenuCallback = Callable[..., object]
MenuDefinition = Mapping[str, None | MenuCallback | type[QMenu]]

class MenuPath(str):
    def __new__(cls, value:str, separator:str='.'):
        return str.__new__(cls, value)
    def __init__(self, value:str, separator:str='.'):
        self.separator = separator    
        
    @property
    def parent(self)-> "MenuPath":
        if self.separator in self:
            return MenuPath(self.rsplit(self.separator, 1)[0], separator=self.separator)
        return MenuPath('', separator=self.separator)  # Return a empty MenuPath if no parent exists
    @property
    def parts(self)-> list[str]:
        return self.split(self.separator)
    def __truediv__(self, other:str)-> "MenuPath":
        if not self:
            return MenuPath(other, separator=self.separator)
        return MenuPath(f"{self}{self.separator}{other}", separator=self.separator)

def initialize_menu(
        main: QMainWindow, menu_def: MenuDefinition, root_menu:QMenu|QMenuBar|None=None, root_menu_name:str='menu',
        tr: Callable[[str], str] = lambda x: x
    ) -> dict[str, QMenu|QAction]:
        """Initialize menu and submenus from a *Flat* dictionary definition.
        
        Arguments:
            menu_def (Mapping[str, None | Callable | type[QMenu]]): 
                A flat dictionary where keys are menu item names.
                Values are either None for placeholders, callables for actions,
                or QMenu for submenu placeholders.
            root_menu (QMenu, optional):
                The parent menu to which the defined menu items will be added.
                If None, the menu items will be added to the main window's menu bar.
            root_menu_name (str, optional):
                The base name for translation keys for the menu items. Default is 'menu'.
        Example:
        ```
            menu_def = {
                "file.save": save_function,
                "file.load": load_function,
                "edit.undo": undo_function,
                "edit.redo": redo_function,
            }
            
        ```
        creates a menu structure like (this is not the return):
        ```
            {
                "File": { "Save": save_function, "Load": load_function },
                "Edit": { "Undo": undo_function, "Redo": redo_function }
            }
        Return:
            dict[str, QMenu|QAction]: A `flat` dictionary mapping menu item names to their corresponding QMenu or QAction objects for further manipulation if needed.
        """
        root_menu_name = MenuPath(root_menu_name)
        if root_menu is None:
            root_menu = main.menuBar()
        menus = {}
        for menu_path, func in menu_def.items():
            splits = menu_path.split('$n:')
            if len(splits) == 2:
                menu_path, display_name = splits
            else:
                display_name =tr(root_menu_name/menu_path)
            
            menu_path = MenuPath(menu_path)
            if menu_path.parent == MenuPath('') and menu_path not in menus: # Top level action
                if func is QMenu:
                    action = menus[menu_path] = root_menu.addMenu(display_name)
                else:
                    action = menus[menu_path] = QAction(display_name, main)
                    root_menu.addAction(action)
            else:
                path = MenuPath('')
                parent_menu = root_menu
                for part in menu_path.parts[:-1]:
                    path /= part
                    if path not in menus:
                        # initialize parent menu if it doesn't exist
                        parent_menu = menus[path] = parent_menu.addMenu(tr(root_menu_name/path))
                    else:
                        parent_menu = menus[path]
                if func is QMenu:
                    action = menus[menu_path] = parent_menu.addMenu(display_name)
                else:
                    action = menus[menu_path] = QAction(display_name, main)
                    parent_menu.addAction(action)
            if func is not None and func is not QMenu:
                action.triggered.connect(cast(MenuCallback, func))
        return menus
