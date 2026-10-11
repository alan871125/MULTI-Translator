import logging
from pathlib import Path
from lxml import etree as ET
from typing import Any, Iterable, Optional
from .version import VERSION
logger = logging.getLogger(__name__)
def load_about_xml(mod:Path)-> Optional[ET._ElementTree|Any]:
    about_path = mod/"About/About.xml"
    if not about_path.exists():
        logger.info(f"About.xml not found in {mod}.")
        return None
    return ET.parse(about_path)

def write_about_xml(
    mod_output_dir:Path, name:str, packageID:str, 
    author:str = 'Unknown', load_after: list[str]=[],
    supported_versions: list[str]=['1.6'], 
    description:str = ''
):
    """Write an About.xml file for the converted mod."""
    about_path = mod_output_dir/"About/About.xml"
    about_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("ModMetaData")
    name_elem = ET.SubElement(root, "name")
    name_elem.text = name
    package_id_elem = ET.SubElement(root, "packageId")
    package_id_elem.text = packageID
    author_elem = ET.SubElement(root, "author")
    author_elem.text = author
    supported_versions_elem = ET.SubElement(root, "supportedVersions")
    for version in supported_versions:
        li_elem = ET.SubElement(supported_versions_elem, "li")
        li_elem.text = version
    load_after_elem = ET.SubElement(root, "loadAfter")
    for mod in load_after:
        li_elem = ET.SubElement(load_after_elem, "li")
        li_elem.text = mod
    description_elem = ET.SubElement(root, "description")
    description_elem.text = description
    tree = ET.ElementTree(root)
    tree.write(about_path, encoding="utf-8", xml_declaration=True, pretty_print=True)

def read_load_folders_xml(mod:Path) -> Optional[ET._ElementTree|Any]:
    """Read a loadFolders.xml file for the converted mod."""
    load_folders_path = mod/"loadFolders.xml"
    if not load_folders_path.exists():
        logger.info(f"loadFolders.xml not found in {mod}.")
        return None
    tree = ET.parse(load_folders_path)
    return tree

def write_load_folders_xml(mod:Path, subfolders:list[Path]|dict[str,list[Path]], version:str=VERSION):
    """Create a loadFolders.xml file for the translations
    Example:
    ```
        <?xml version="1.0" encoding="utf-8"?>
        <loadFolders>
            <v1.6>
                <li>/</li>
                <li IfModActive="package.id">Subfolder1</li>
                <li>Subfolder2</li>
            </v1.6>
        </loadFolders>
    ```
    """
    #TODO: If is a dict, it can also be be tuple[str]:list[Path], used to specify that this subfolder has multiple dependencies.
    load_folders_path = mod/"loadFolders.xml"
    root = ET.Element("loadFolders")
    version_elem = ET.SubElement(root, f"v{version}")
    if isinstance(subfolders, dict):
        for package_id, _subfolders in subfolders.items():
            for subfolder in _subfolders:
                li_elem = ET.SubElement(version_elem, "li", IfModActive=package_id)
                li_elem.text = subfolder.as_posix() if subfolder != Path(".") else "/"
    else:
        for subfolder in subfolders:
            li_elem = ET.SubElement(version_elem, "li")
            li_elem.text = subfolder.as_posix() if subfolder != Path(".") else "/"
    tree = ET.ElementTree(root)
    tree.write(load_folders_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    return tree