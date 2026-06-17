"""
Menu initialization utility for PyQt5 applications.
"""

from typing import Callable, Mapping, Optional
from PyQt5.QtWidgets import QMenu, QAction, QMenuBar

MenuDefinition = Mapping[str, Optional[Callable|QAction|QMenu|str]]  # The value can be a callback, a QAction, a QMenu, or a special string like '$separator' or '$menu']

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
        menu_def: MenuDefinition, root_menu:QMenu|QMenuBar, root_menu_name:str='menu',
        tr: Callable[[str], str] = lambda x: x
    ) -> dict[str, QMenu|QAction]:
        """Initialize menu and submenus from a *Flat* dictionary definition.  
        
        ## Speciall indicators in the menu_def
            - key: "$n:MenuName" -> The menu item will be displayed as "MenuName" but the translation key will be based on the actual menu path. This is useful for items that need to display dynamic content like file paths.
            - value: "$separator" -> The menu item will be a separator. This is useful for visually grouping related menu items together.
            - value: "$menu" -> The menu item is a submenu placeholder, and will be initialized as an actual QMenu object. The display name will be based on the menu path. This is useful for quickly defining submenus without needing to specify display names.
        Arguments:
            menu_def (Mapping[str, None | Callable | type[QMenu]]): 
                A flat dictionary where keys are menu item names.
                Values are either None for placeholders, callables for actions,
                or QMenu for submenu placeholders.
            root_menu (QMenu | QMenuBar):
                The parent menu or menu bar to which the defined menu items will be added.
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
        menus = {}
        for menu_path, menu_item in menu_def.items():
            splits = menu_path.split('$n:')
            if len(splits) == 2:
                menu_path, display_name = splits
            else:
                display_name =tr(root_menu_name/menu_path)
            
            menu_path = MenuPath(menu_path)
            
            path = MenuPath('')
            parent_menu = root_menu
            # Walk through the menu path to create submenus as needed
            for part in menu_path.parts[:-1]:
                path /= part
                if path not in menus:
                    # initialize parent menu if it doesn't exist
                    parent_menu = menus[path] = parent_menu.addMenu(tr(root_menu_name/path))
                else:
                    parent_menu = menus[path]
            # Create the final menu item corresponding to the menu_item
            if isinstance(menu_item, QMenu):
                action = menus[menu_path] = parent_menu.addMenu(menu_item)
            elif isinstance(menu_item, str) and menu_item == '$menu':
                action = menus[menu_path] = parent_menu.addMenu(display_name)
            elif isinstance(menu_item, str) and menu_item == '$separator':
                action = menus[menu_path] = parent_menu.addSeparator()
            elif isinstance(menu_item, QAction):
                action = menus[menu_path] = menu_item
                parent_menu.addAction(action)
            else:
                action = menus[menu_path] = QAction(display_name, parent_menu)
                parent_menu.addAction(action)
            if menu_item is not None and isinstance(menu_item, Callable):
                action.triggered.connect(menu_item)
        return menus
