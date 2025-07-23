#!/usr/bin/env python3
"""
Generate markdown documentation for all atopile library components, interfaces, and traits.
Uses AST parsing to extract real docstrings and information from source files.
"""

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import importlib
import inspect

import faebryk.library._F as F


from faebryk.core.node import Node
from faebryk.core.module import Module
from faebryk.core.moduleinterface import ModuleInterface
from faebryk.core.trait import Trait
from faebryk.core.parameter import Parameter

from atopile.mcp.tools.library import _get_library_node, _get_library_nodes

# Base path to the atopile library source
LIBRARY_PATH = Path(__file__).parent.parent / "atopile" / "src" / "faebryk" / "library"
ATTRIBUTES_PATH = Path(__file__).parent.parent / "atopile" / "src" / "atopile" / "attributes.py"
BASE_DOC_PATH = Path(__file__).parent / "atopile" / "api-reference"

doc_types = {
    'component': Module,
    'interface': ModuleInterface,
    'trait': Trait
}

icons = {
    'component': 'microchip',
    'interface': 'right-left',
    'trait': 'right-left'
}

data_types = {
    'parameter': Parameter,
    'interface': ModuleInterface,
    'trait': Trait
}

# Not all traits are functional or reasonable to expose to users
functional_trait_names = [
    'can_bridge',
    'can_bridge_by_name',
    'has_single_electric_reference',
    'is_pickable',
    'requires_pulls',
]
excluded_attributes = {"datasheet_url", "designator_prefix", "footprint", "suggest_net_name"}

def create_library_node(name: str, t: type[Node] = Node) -> Node:
    if name not in F.__dict__: # name of the module to be searched in the imports of the internal namespace __dict__ of _F imports
        raise ValueError(f"Type {name} not found")

    m = F.__dict__[name]

    if not isinstance(m, type) or not issubclass(m, t):
        raise ValueError(f"Type {name} is not a valid {t.__name__}")

    # get file of module
    file = m.__module__
    if file is None:
        raise ValueError(f"Type {name} is not part of a module")

    module = importlib.import_module(file)

    if module.__file__ is None:
        raise ValueError(f"Type {name} has no file")

    # Get the class from the module and instantiate it
    module_class = getattr(module, name)
    if not isinstance(module_class, type):
        raise ValueError(f"{name} is not a class")
    
    # Instantiate the class object
    node = module_class()

    return node

def get_global_attributes():
    from atopile.attributes import GlobalAttributes
    props = [{"name": "GlobalAttributes", "doc": GlobalAttributes.__doc__, "type": "GlobalAttributes"}]
    for name, obj in vars(GlobalAttributes).items():
        if isinstance(obj, property):
            doc = inspect.getdoc(obj.fget) if obj.fget else ""
            arg_type = None
            if obj.fset:
                try:
                    sig = inspect.signature(obj.fset)
                    # skip 'self', get 'value'
                    for param in list(sig.parameters.values())[1:]:
                        arg_type = param.annotation
                        break
                except ValueError:
                    pass
            props.append({
                "name": name,
                "type": arg_type,
                "doc": doc
            })
    return props

def extract_module_info(module_name: str) -> Optional[Dict[str, Any]]:
    """Extract detailed information from a module file."""
    module_file = LIBRARY_PATH / f"{module_name}.py"
    
    if not module_file.exists():
        print(f"module file not found: {module_file}")
        return None
    
    try:
        with open(module_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Find the module class
        for node in ast.walk(tree):
            print(type(node))
            if isinstance(node, ast.ClassDef) and node.name == module_name:
                module_info = {
                    "name": module_name,
                    "docstring": ast.get_docstring(node),
                    "parameters": [],
                    "traits": [],
                    "properties": [],
                    "interfaces": []
                }
                
                # Extract class body items and look for docstrings after assignments
                for i, item in enumerate(node.body):
                    if isinstance(item, ast.Assign):
                        # Extract field assignments
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                field_name = target.id
                                
                                # Look for docstring in the next item
                                field_docstring = None
                                if i + 1 < len(node.body):
                                    next_item = node.body[i + 1]
                                    if isinstance(next_item, ast.Expr) and isinstance(next_item.value, ast.Constant):
                                        if isinstance(next_item.value.value, str):
                                            field_docstring = next_item.value.value.strip()
                                
                                field_info = analyze_field_assignment(item, field_name, field_docstring)
                                if field_info:
                                    if field_info["type"] == "parameter":
                                        module_info["parameters"].append(field_info)
                                    elif field_info["type"] == "interface":
                                        module_info["interfaces"].append(field_info)
                    
                    elif isinstance(item, ast.AnnAssign):
                        # Handle annotated assignments like "scl: F.ElectricLogic"
                        if isinstance(item.target, ast.Name):
                            field_name = item.target.id
                            
                            # Look for docstring in the next item
                            field_docstring = None
                            if i + 1 < len(node.body):
                                next_item = node.body[i + 1]
                                if isinstance(next_item, ast.Expr) and isinstance(next_item.value, ast.Constant):
                                    if isinstance(next_item.value.value, str):
                                        field_docstring = next_item.value.value.strip()
                            
                            # Extract type annotation information
                            field_info = analyze_annotated_assignment(item, field_name, field_docstring)
                            if field_info:
                                if field_info["type"] == "interface":
                                    module_info["interfaces"].append(field_info)
                    
                    elif isinstance(item, ast.FunctionDef):
                        if item.name.startswith('__'):
                            continue
                        
                        func_info = {
                            "name": item.name,
                            "docstring": ast.get_docstring(item),
                            "decorator": get_function_decorator(item)
                        }
                        
                        # Categorize based on decorator and name
                        if func_info["decorator"] == "property":
                            module_info["properties"].append(func_info)
                        elif (func_info["decorator"] == "L.rt_field" and is_rt_field_returning_trait(item)) or item.name in ['pickable', 'can_bridge', 'simple_value_representation']:
                            module_info["traits"].append(func_info)
                
                return module_info
                
    except Exception as e:
        print(f"Error parsing {module_name} file: {e}")
        return None

def analyze_field_assignment(node: ast.Assign, field_name: str, docstring: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Analyze a field assignment to determine its type and properties."""
    try:
        # Convert the AST node to string for analysis
        if hasattr(ast, 'unparse'):
            value_str = ast.unparse(node.value)
        else:
            value_str = str(node.value)
        
        # Parameter fields (L.p_field)
        if 'L.p_field' in value_str:
            units = extract_units_from_assignment(value_str)
            return {
                "name": field_name,
                "type": "parameter",
                "units": units,
                "description": docstring.strip() if docstring and docstring.strip() else ""
            }
        
        # List fields (like unnamed interfaces)
        elif 'L.list_field' in value_str:
            count, interface_type = extract_list_field_info(value_str)
            return {
                "name": field_name,
                "type": "interface",
                "count": count,
                "interface_type": interface_type,
                "description": docstring.strip() if docstring and docstring.strip() else ""
            }
            
    except Exception as e:
        print(f"    Error analyzing field {field_name}: {e}")
    
    return None

def analyze_annotated_assignment(node: ast.AnnAssign, field_name: str, docstring: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Analyze an annotated assignment (like 'scl: F.ElectricLogic') to determine its type and properties."""
    try:
        # Extract the type annotation from the AnnAssign node
        type_annotation = node.annotation
        
        # Handle ast.Attribute nodes (like F.ElectricLogic)
        if isinstance(type_annotation, ast.Attribute):
            # Extract the interface type from F.InterfaceType
            if isinstance(type_annotation.value, ast.Name) and type_annotation.value.id == 'F':
                interface_type = type_annotation.attr
                return {
                    "name": field_name,
                    "type": "interface", 
                    "interface_type": interface_type,
                    "description": docstring.strip() if docstring and docstring.strip() else ""
                }
        
        # Handle ast.Name nodes (simple type names)
        elif isinstance(type_annotation, ast.Name):
            return {
                "name": field_name,
                "type": "interface",
                "interface_type": type_annotation.id,
                "description": docstring.strip() if docstring and docstring.strip() else ""
            }
        
        # Fallback: convert to string and try to parse
        else:
            if hasattr(ast, 'unparse'):
                type_annotation_str = ast.unparse(type_annotation)
            else:
                type_annotation_str = str(type_annotation)
            
            # Handle F.InterfaceType pattern
            if 'F.' in type_annotation_str:
                interface_type = type_annotation_str.replace('F.', '').strip()
                return {
                    "name": field_name,
                    "type": "interface",
                    "interface_type": interface_type,
                    "description": docstring.strip() if docstring and docstring.strip() else ""
                }
             
    except Exception as e:
        print(f"    Error analyzing annotated field {field_name}: {e}")
    
    return None

def extract_units_from_assignment(value_str: str) -> Optional[str]:
    """Extract units from a parameter field assignment."""
    units_match = re.search(r'units=P\.(\w+)', value_str)
    return units_match.group(1) if units_match else None

def extract_list_field_info(value_str: str) -> tuple:
    """Extract count and type from list field assignment."""
    # L.list_field(2, F.Electrical) -> (2, "Electrical")
    count_match = re.search(r'L\.list_field\((\d+)', value_str)
    type_match = re.search(r'F\.(\w+)', value_str)
    
    count = int(count_match.group(1)) if count_match else 1
    interface_type = type_match.group(1) if type_match else "Unknown"
    
    return count, interface_type

def get_function_decorator(node: ast.FunctionDef) -> Optional[str]:
    """Get the primary decorator of a function."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            if hasattr(decorator.value, 'id'):
                return f"{decorator.value.id}.{decorator.attr}"
            else:
                return decorator.attr
    return None

def is_rt_field_returning_trait(node: ast.FunctionDef) -> bool:
    """Check if an @L.rt_field method actually returns a trait."""
    try:
        # Look for return statements in the method body
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Return) and stmt.value:
                return_value = ast.unparse(stmt.value)
                
                # Check if the return value looks like a trait
                # Trait patterns: F.has_*, F.is_*, F.can_*, etc. - including constructor calls
                trait_patterns = [
                    r'F\.has_\w+(_defined|_impl)?\s*\(',  # F.has_*_defined(...) or F.has_*(...)
                    r'F\.is_\w+(_defined|_impl)?\s*\(',   # F.is_*_defined(...) or F.is_*(...)
                    r'F\.can_\w+(_defined|_impl)?\s*\(',  # F.can_*_defined(...) or F.can_*(...)
                    r'F\.requires_\w+(_defined|_impl)?\s*\(',  # F.requires_*
                    r'F\.implements_\w+(_defined|_impl)?\s*\('  # F.implements_*
                ]
                
                # First check for trait patterns - if it starts with a trait pattern, it's a trait
                for pattern in trait_patterns:
                    if re.match(pattern, return_value.strip()):  # Use match to check from beginning
                        return True
                
                # If return value contains trait-like suffixes at the start
                if re.match(r'.*_defined\s*\(', return_value.strip()) or re.match(r'.*_impl\s*\(', return_value.strip()):
                    return True
                
                # Non-trait patterns that should be excluded (only if they are the main return, not arguments)
                non_trait_patterns = [
                    r'^times\s*\(',                    # Starts with times(
                    r'^F\.ElectricLogic\b',             # Starts with F.ElectricLogic
                    r'^F\.ElectricPower\b',             # Starts with F.ElectricPower
                    r'^F\.Electrical\b',                # Starts with F.Electrical
                    r'^F\.I2C\b',                       # Starts with F.I2C
                    r'^F\.SPI\b',                       # Starts with F.SPI
                    r'^F\.UART\b',                      # Starts with F.UART
                    r'^F\.PWM\b',                       # Starts with F.PWM
                    r'^F\.ADC\b',                       # Starts with F.ADC
                    r'^F\.DAC\b',                       # Starts with F.DAC
                    r'^.*\.get\s*\(',                   # Starts with *.get(
                    r'^.*\.set\s*\(',                   # Starts with *.set(
                    r'^.*\[\s*\d+\s*\]',               # Starts with array indexing
                    r'^range\s*\(',                     # Starts with range(
                    r'^list\s*\(',                      # Starts with list(
                    r'^dict\s*\(',                      # Starts with dict(
                    r'^super\s*\(',                     # Starts with super(
                    r'^self\.\w+\s*\(',                 # Starts with self.method(
                ]
                
                # Check for non-trait patterns
                for pattern in non_trait_patterns:
                    if re.match(pattern, return_value.strip()):
                        return False
                
        return False
        
    except Exception:
        # If we can't parse it, default to False to be safe
        return False

def get_trait_description(trait_name: str) -> str:
    """Get descriptive text for traits from their actual source files."""
    
    # Path to the trait file in the atopile source  
    trait_file_path = LIBRARY_PATH / f"{trait_name}.py"
    if not trait_file_path.exists():
        return ""
    try:
        with open(trait_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        # Find the class definition and extract its docstring
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                docstring = ast.get_docstring(node)
                if docstring and docstring.strip():
                    return docstring.strip()
        return ""
        
    except Exception as e:
        print(f"Error reading trait file {trait_name}.py: {e}")
        return ""



def append_mkdn_attributes(param)-> str:
    param_name = param["name"]
    param_units = param["type"]
    param_desc = param["doc"] 
    
    # Add unit info to the type
    param_type = param_units if param_units else "string"
    
    # Only include description if it's not empty
    if param_desc:
        return f"<ParamField path='{param_name}' type='{param_type}'>\n\n{param_desc}\n</ParamField>\n\n"
    else:
        return f"<ParamField path='{param_name}' type='{param_type}'>\n</ParamField>\n\n"

def append_mkdn_parameter(param: Parameter)-> str:
    param_name = param.get_name()
    param_units = param.units
    param_desc = param.__doc__ or ""
    
    # Add unit info to the type
    param_type = param_units if param_units else "string"
    
    # Only include description if it's not empty
    if param_desc.strip():
        return f"<ParamField path='{param_name}' type='{param_type}'>\n\n{param_desc}\n</ParamField>\n\n"
    else:
        return f"<ParamField path='{param_name}' type='{param_type}'>\n</ParamField>\n\n"
# Generate one parameter line in a page
def append_mkdn_interface(param: ModuleInterface)-> str:
    param_name = param.get_name()
    param_desc = param.__doc__ or ""
    if_type = type(param)
    
    # Only include description if it's not empty
    if param_desc.strip():
        return f"<ParamField path='{param_name}' type='{if_type}'>\n\n{param_desc}\n</ParamField>\n\n"
    else:
        return f"<ParamField path='{param_name}' type='{if_type}'>\n</ParamField>\n\n"

# Generate one trait line in a page
def append_mkdn_trait(trait: Node)-> str:
    trait_name = trait.__class__.__name__
    trait_desc = get_trait_description(trait_name)
    
    # Get the actual trait class name for proper linking
    trait_url_name = trait_name.replace("_", "-")
    trait_link = f"/atopile/api-reference/traits/{trait_url_name}"
    traits_m = ""
    if trait_name in functional_trait_names:
        traits_m += f"[{trait_name}]({trait_link})\n\n"
    else:
        traits_m += f"**{trait_name}**\n\n"
    if trait_desc.strip():
        traits_m += f"{trait_desc}\n\n"
    return traits_m

# Generate one page of documentation
def generate_node_markdown(node_data: Dict[str, Any], icon_name: str, global_attributes: List[Dict[str, Any]], global_attributes_docstring: Optional[str]) -> str:
    """Generate the complete markdown documentation for a module."""
    
    node_name = node_data["name"]
    
    # Build parameters section
    parameters_md = ""
    if node_data.get("parameters"):
        parameters_md = "\n## Parameters\n\n"
        for param in node_data["parameters"]:
            parameters_md += append_mkdn_parameter(param)

    # Build interfaces section  
    interfaces_md = ""
    if node_data.get("interfaces"):
        interfaces_md = "\n## Interfaces\n\n"
        for interface in node_data["interfaces"]:
            interfaces_md += append_mkdn_interface(interface)

    # Build traits section
    traits_md = ""
    if node_data.get("traits"):
        traits_md = "\n## Traits\n\n"
        for trait in node_data["traits"]:
            traits_md += append_mkdn_trait(trait)


    # Build global attributes section
    global_attributes_md = ""
    if global_attributes:
        # Filter out specific attributes that shouldn't be in docs
        filtered_attributes = [attr for attr in global_attributes 
                              if attr["name"] not in excluded_attributes]
        if filtered_attributes:  # Only create section if there are attributes to show
            global_attributes_md = "\n## Global Attributes\n\n"
            # Add class docstring if available
            if global_attributes_docstring and global_attributes_docstring.strip():
                global_attributes_md += f"{global_attributes_docstring.strip()}\n\n"
            for attr in filtered_attributes:
                attr['description'] = attr.get("docstring", "")
                global_attributes_md += append_mkdn_attributes(attr)

    # module description
    description = node_data.get("docstring", "")
    
    # Generate the complete markdown
    markdown = f'---\n\ntitle: "{node_name}"\nicon: {icon_name}\ndescription: "{description}"\n---\n\n{parameters_md}{interfaces_md}{traits_md}{global_attributes_md}'

    return markdown

def generate_trait_markdown(trait_name: str) -> str:
    """Generate markdown for a trait."""
    description = get_trait_description(trait_name)
    
    # Only use description if we actually found a docstring
    if not description:
        description = ""
    
    return f"""---\n\ntitle: "{trait_name}"\nicon: "fingerprint"\ndescription: "{description}"\n---\n\n"""

def clear_existing_docs():
    """Clear existing documentation files in components, interfaces, and traits directories."""
    base_path = Path(__file__).parent / "atopile" / "api-reference"
    
    directories_to_clear = ["components", "interfaces", "traits"]
    total_cleared = 0
    
    for dir_name in directories_to_clear:
        dir_path = base_path / dir_name
        if dir_path.exists():
            # Count existing files
            existing_files = list(dir_path.glob("*.mdx"))
            file_count = len(existing_files)
            
            # Remove all .mdx files
            for file_path in existing_files:
                if file_path.is_file():
                    file_path.unlink()
            
            print(f"🗑️  Cleared {file_count} files from {dir_name}/")
            total_cleared += file_count
        else:
            print(f"📁 Created directory {dir_name}/")
            dir_path.mkdir(parents=True, exist_ok=True)
    
    if total_cleared > 0:
        print(f"✅ Total cleared: {total_cleared} files\n")
    else:
        print("✅ No existing files to clear\n")

def generate_all_docs():
    """Generate documentation for all library components, interfaces, and traits."""
    clear_existing_docs()
    
    # Get global attributes
    global_attributes = get_global_attributes()
    
    # Get all library files
    for doc_name, node_type in doc_types.items():
        node_info_list = _get_library_nodes(t=node_type)
        base_file_path = BASE_DOC_PATH / doc_name
        base_file_path.mkdir(parents=True, exist_ok=True)
        for node_info in node_info_list:
            node = create_library_node(node_info.name, t=node_type)
            node_data = {}
            node_data["name"] = node_info.name
            node_data["docstring"] = node_info.docstring
            node_data["parameters"] = node.get_children(direct_only=False, types=Parameter, include_root=False)
            node_data["interfaces"] = node.get_children(direct_only=False, types=ModuleInterface, include_root=False)
            node_data["traits"] = node.get_children(direct_only=False, types=Trait, include_root=False)
            node_data["modules"] = node.get_children(direct_only=False, types=Module, include_root=False)
            doc_file_path = base_file_path / f"{node_info.name.lower()}.mdx"
            # doc_file_path.mkdir(parents=True, exist_ok=True)
            content = generate_node_markdown(node_data, icons[doc_name], global_attributes, None)
            with open(doc_file_path, 'w') as f:
                f.write(content)

def update_navigation():
    """Update docs.json Library Reference section with only existing files in api-reference folder."""
    docs_json_path = Path(__file__).parent / "docs.json"
    
    # Read the existing docs.json
    with open(docs_json_path) as f:
        docs_config = json.load(f)
    
    # Scan actual folders for .mdx files and validate they exist
    base_path = Path(__file__).parent / "atopile" / "api-reference"
    
    # First, check what's currently in docs.json and validate if those files exist
    current_missing_files = []
    for tab in docs_config["navigation"]["tabs"]:
        if tab["tab"] == "atopile":
            for group in tab["groups"]:
                if group["group"] == "Library Reference":
                    for page_group in group.get("pages", []):
                        if isinstance(page_group, dict) and "pages" in page_group:
                            for page_path in page_group["pages"]:
                                # Convert docs.json path to actual file path
                                if page_path.startswith("atopile/api-reference/"):
                                    relative_path = page_path.replace("atopile/api-reference/", "")
                                    actual_file_path = base_path / f"{relative_path}.mdx"
                                    if not actual_file_path.exists():
                                        current_missing_files.append(page_path)
    
    if current_missing_files:
        print(f"🗑️  Found {len(current_missing_files)} missing files in current docs.json:")
        for missing_file in current_missing_files[:10]:  # Show first 10
            print(f"   - {missing_file}")
        if len(current_missing_files) > 10:
            print(f"   ... and {len(current_missing_files) - 10} more")
        print("   These will be removed from navigation.\n")
    else:
        print("✅ All files in current docs.json exist in filesystem\n")
    
    # Get components pages - only include files that actually exist
    components_pages = []
    components_path = base_path / "components"
    if components_path.exists():
        for file_path in sorted(components_path.glob("*.mdx")):
            if file_path.is_file() and file_path.exists():
                components_pages.append(f"atopile/api-reference/components/{file_path.stem}")
    
    # Get interfaces pages - only include files that actually exist
    interfaces_pages = []
    interfaces_path = base_path / "interfaces"
    if interfaces_path.exists():
        for file_path in sorted(interfaces_path.glob("*.mdx")):
            if file_path.is_file() and file_path.exists():
                interfaces_pages.append(f"atopile/api-reference/interfaces/{file_path.stem}")
    
    # Get traits pages - only include files that actually exist
    traits_pages = []
    traits_path = base_path / "traits"
    if traits_path.exists():
        for file_path in sorted(traits_path.glob("*.mdx")):
            if file_path.is_file() and file_path.exists():
                traits_pages.append(f"atopile/api-reference/traits/{file_path.stem}")
    
    # Find and completely replace the Library Reference group
    library_reference_found = False
    for tab in docs_config["navigation"]["tabs"]:
        if tab["tab"] == "atopile":
            for group in tab["groups"]:
                if group["group"] == "Library Reference":
                    library_reference_found = True
                    
                    # Store old counts for comparison
                    old_pages = group.get("pages", [])
                    old_component_count = 0
                    old_interface_count = 0
                    old_trait_count = 0
                    
                    for page_group in old_pages:
                        if isinstance(page_group, dict):
                            if page_group.get("group") == "Components":
                                old_component_count = len(page_group.get("pages", []))
                            elif page_group.get("group") == "Interfaces":
                                old_interface_count = len(page_group.get("pages", []))
                            elif page_group.get("group") == "Traits":
                                old_trait_count = len(page_group.get("pages", []))
                    
                    # Completely replace the Library Reference section with only existing files
                    group["pages"] = [
                        {
                            "group": "Components",
                            "pages": components_pages
                        },
                        {
                            "group": "Interfaces", 
                            "pages": interfaces_pages
                        },
                        {
                            "group": "Traits",
                            "pages": traits_pages
                        }
                    ]
                    
                    print(f"Updated Library Reference section:")
                    print(f"  Components: {old_component_count} → {len(components_pages)} pages")
                    print(f"  Interfaces: {old_interface_count} → {len(interfaces_pages)} pages") 
                    print(f"  Traits: {old_trait_count} → {len(traits_pages)} pages")
                    
                    # Report any significant changes
                    if old_component_count != len(components_pages):
                        diff = len(components_pages) - old_component_count
                        print(f"  📝 Components: {'+' if diff > 0 else ''}{diff} files")
                    if old_interface_count != len(interfaces_pages):
                        diff = len(interfaces_pages) - old_interface_count
                        print(f"  📝 Interfaces: {'+' if diff > 0 else ''}{diff} files")
                    if old_trait_count != len(traits_pages):
                        diff = len(traits_pages) - old_trait_count
                        print(f"  📝 Traits: {'+' if diff > 0 else ''}{diff} files")
                    
                    break
            break
    
    if not library_reference_found:
        print("⚠️  Warning: Library Reference section not found in docs.json")
        return
    
    # Write back the updated config (preserving everything else)
    with open(docs_json_path, 'w') as f:
        json.dump(docs_config, f, indent=2)
    
    print("\n✅ Updated navigation in docs.json")
    print(f"📁 Scanned: {base_path}")
    print("🔄 Only existing .mdx files are included in navigation")

if __name__ == "__main__":
    print(get_global_attributes())
    generate_all_docs()
    # update_navigation()