"""
This module is for analyzing RimWolrd XML files to find translatable text.
Find the results in translatable_records.py, which contains a dictionary of translatable fields for each RimWorld Def type.
"""

from typing import Any, Optional

from core.text_unit import TextUnit
from pathlib import Path
from core.json_path import JsonPath
from lxml import etree as ET
from core.engines.rimworld import translatable_records

def node_walk(root: ET._Element, path_to_node: Optional[list[str]] = None):
    path_to_node = path_to_node or []
    for i, child in enumerate(root.iterchildren()):
        if child.tag == "li":
            current_path = path_to_node + [str(i)]
        else:
            current_path = path_to_node + [child.tag]
        yield current_path, child
        if len(child) > 0:
            yield from node_walk(child, current_path)

def extract_translatable(path: Path|str, json_prefix: Optional[list] = None, root_dir: Optional[Path|str] = None) -> list[TextUnit]:
    """Extract translatable text from an XML file."""
    path = Path(path)
    root_dir = Path(root_dir) if root_dir else path.parent
    json_prefix = json_prefix or []
    tree = ET.parse(path)
    root = tree.getroot() # tag: Defs
    out: list[TextUnit] = []
    for c in root.iterchildren():
        deftype = c.tag
        defname = c.find("defName")
        if defname is None:
            continue
        
        _translatable_fields = translatable_records.get_translatable_fields(deftype)
        indexed_translatable_fields = {
            f[:-6]: f for f in _translatable_fields if f.endswith(".{idx}")
        }
        # walk the children of c to find translatable fields

        for node_path, node in node_walk(c, path_to_node=[str(defname.text)]):
            # check if the node is a translatable field for this deftype
            if node_path[-1] in _translatable_fields and len(node) == 0:
                # check if the node is a translatable field for this deftype
                key = JsonPath(json_prefix+[deftype]+['.'.join(node_path)])
                out.append(TextUnit(
                    file=path.relative_to(root_dir).as_posix(),
                    key=key,
                    original=node.text or "",
                    translation=node.text or "",
                ))
            elif node.tag =='li' and node_path[-2] in indexed_translatable_fields:
                # check if the node is a translatable field for this deftype
                key = JsonPath(json_prefix+[deftype]+['.'.join(node_path)])
                out.append(TextUnit(
                    file=path.relative_to(root_dir).as_posix(),
                    key=key,
                    original=node.text or "",
                    translation=node.text or "",
                ))
    return out

if __name__ == "__main__":
    import pandas as pd
    path = Path(r"D:\SteamLibrary\steamapps\common\RimWorld\Data\Core\Defs\RulePackDefs\RulePacks_Damage.xml")
    translatable = extract_translatable(path)
    print(pd.DataFrame(translatable).head())
    pass