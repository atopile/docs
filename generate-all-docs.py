#!/usr/bin/env python3
"""
Generate markdown documentation for all atopile library components, interfaces, and traits.
Uses AST parsing to extract real docstrings and information from source files.
"""

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Base path to the atopile library source
LIBRARY_PATH = Path("/Users/nicholaskrstevski/github/atopile/src/faebryk/library")
ATTRIBUTES_PATH = Path("/Users/nicholaskrstevski/github/atopile/src/atopile/attributes.py")

functional_trait_names = [
    'can_bridge',
    'can_bridge_by_name',
    'has_single_electric_reference',
    'is_pickable'
]

def extract_component_info(component_name: str) -> Optional[Dict[str, Any]]:
    """Extract detailed information from a component file."""
    component_file = LIBRARY_PATH / f"{component_name}.py"
    
    if not component_file.exists():
        print(f"Component file not found: {component_file}")
        return None
    
    try:
        with open(component_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Find the component class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == component_name:
                component_info = {
                    "name": component_name,
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
                                        component_info["parameters"].append(field_info)
                                    elif field_info["type"] == "interface":
                                        component_info["interfaces"].append(field_info)
                    
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
                                    component_info["interfaces"].append(field_info)
                    
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
                            component_info["properties"].append(func_info)
                        elif (func_info["decorator"] == "L.rt_field" and is_rt_field_returning_trait(item)) or item.name in ['pickable', 'can_bridge', 'simple_value_representation']:
                            component_info["traits"].append(func_info)
                
                return component_info
                
    except Exception as e:
        print(f"Error parsing {component_name} file: {e}")
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

def extract_global_attributes() -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Extract global attributes from the GlobalAttributes class."""
    
    if not ATTRIBUTES_PATH.exists():
        print(f"GlobalAttributes file not found: {ATTRIBUTES_PATH}")
        return [], None
    
    try:
        with open(ATTRIBUTES_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        attributes = []
        class_docstring = None
        
        # Find the GlobalAttributes class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "GlobalAttributes":
                
                # Extract the class docstring
                class_docstring = ast.get_docstring(node)
                
                # Look for property methods (getters)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and len(item.decorator_list) > 0:
                        # Check if it's a property
                        for decorator in item.decorator_list:
                            if isinstance(decorator, ast.Name) and decorator.id == "property":
                                attr_name = item.name
                                attr_docstring = ast.get_docstring(item)
                                
                                # Skip private attributes and methods
                                if not attr_name.startswith('_'):
                                    attributes.append({
                                        "name": attr_name,
                                        "docstring": attr_docstring.strip() if attr_docstring else ""
                                    })
                
                return attributes, class_docstring
                
    except Exception as e:
        print(f"Error parsing GlobalAttributes file: {e}")
        return [], None

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

def generate_component_markdown(component_info: Dict[str, Any], global_attributes: List[Dict[str, Any]], global_attributes_docstring: Optional[str]) -> str:
    """Generate the complete markdown documentation for a component."""
    
    component_name = component_info["name"]
    
    # Build parameters section
    parameters_md = ""
    if component_info.get("parameters"):
        parameters_md = "\n## Parameters\n\n"
        for param in component_info["parameters"]:
            param_name = param["name"]
            param_units = param.get("units", "")
            param_desc = param.get("description", "")
            
            # Add unit info to the type
            param_type = param_units if param_units else "string"
            
            # Only include description if it's not empty
            if param_desc.strip():
                parameters_md += f"""<ParamField path="{param_name}" type="{param_type}">
  {param_desc}
</ParamField>

"""
            else:
                parameters_md += f"""<ParamField path="{param_name}" type="{param_type}">
</ParamField>

"""

    # Build interfaces section  
    interfaces_md = ""
    if component_info.get("interfaces"):
        interfaces_md = "\n## Interfaces\n\n"
        for interface in component_info["interfaces"]:
            interface_name = interface["name"]
            interface_desc = interface.get("description", "")
            interface_type = interface.get("interface_type", "Electrical")
            
            if interface.get("count", 1) > 1:
                interface_type = f"{interface_type}[{interface['count']}]"
            
            # Only include description if it's not empty
            if interface_desc.strip():
                interfaces_md += f"""<ParamField path="{interface_name}" type="{interface_type}">
  {interface_desc}
</ParamField>

"""
            else:
                interfaces_md += f"""<ParamField path="{interface_name}" type="{interface_type}">
</ParamField>

"""

    # Build properties section
    properties_md = ""
    if component_info.get("properties"):
        properties_md = "\n## Properties\n\n"
        for prop in component_info["properties"]:
            prop_name = prop["name"]
            prop_desc = prop.get("docstring", "") or ""
            
            # Only include description if it's not empty
            if prop_desc and prop_desc.strip():
                properties_md += f"""<ParamField path="{prop_name}" type="Electrical" readonly>
  {prop_desc}
</ParamField>

"""
            else:
                properties_md += f"""<ParamField path="{prop_name}" type="Electrical" readonly>
</ParamField>

"""

    # Build traits section
    traits_md = ""
    if component_info.get("traits"):
        traits_md = "\n## Traits\n\n"
        for trait in component_info["traits"]:
            trait_name = trait["name"]
            trait_desc = get_trait_description(trait_name)
            
            # Get the actual trait class name for proper linking
            trait_url_name = trait_name.replace("_", "-")
            trait_link = f"/atopile/api-reference/traits/{trait_url_name}"
            
            if trait_desc.strip():
                traits_md += f"[{trait_name}]({trait_link})\n\n{trait_desc}\n\n"
            else:
                traits_md += f"[{trait_name}]({trait_link})\n\n"

    # Build global attributes section
    global_attributes_md = ""
    if global_attributes:
        # Filter out specific attributes that shouldn't be in docs
        excluded_attributes = {"datasheet_url", "designator_prefix", "footprint", "suggest_net_name"}
        filtered_attributes = [attr for attr in global_attributes 
                              if attr["name"] not in excluded_attributes]
        
        if filtered_attributes:  # Only create section if there are attributes to show
            global_attributes_md = "\n## Global Attributes\n\n"
            
            # Add class docstring if available
            if global_attributes_docstring and global_attributes_docstring.strip():
                global_attributes_md += f"{global_attributes_docstring.strip()}\n\n"
            
            for attr in filtered_attributes:
                attr_name = attr["name"]
                attr_desc = attr.get("docstring", "")
                
                # Only include description if it's not empty
                if attr_desc.strip():
                    global_attributes_md += f"""<ParamField path="{attr_name}" type="string">
  {attr_desc}
</ParamField>

"""
                else:
                    global_attributes_md += f"""<ParamField path="{attr_name}" type="string">
</ParamField>

"""

    # Component description
    description = component_info.get("docstring") or ""
    
    # Generate the complete markdown
    markdown = f"""---
title: "{component_name}"
icon: "microchip"
description: "{description}"
---

{parameters_md}{interfaces_md}{properties_md}{traits_md}{global_attributes_md}"""

    return markdown

def generate_interface_markdown(interface_name: str) -> str:
    """Generate markdown for an interface with detailed parameter and field extraction."""
    # Try to extract interface info from source using the same approach as components
    interface_info = extract_component_info(interface_name)
    
    if not interface_info:
        # Fallback to basic extraction if component extraction fails
        interface_file = LIBRARY_PATH / f"{interface_name}.py"
        docstring = ""
        
        if interface_file.exists():
            try:
                with open(interface_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                # Find the interface class
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == interface_name:
                        docstring = ast.get_docstring(node) or ""
                        break
                        
            except Exception as e:
                print(f"Error parsing {interface_name}: {e}")
        
        description = docstring or ""
        
        return f"""---
title: "{interface_name}"
icon: "right-left"
description: "{description}"
---
"""
    
    # Use the extracted component info to generate detailed interface documentation
    description = interface_info.get("docstring") or ""
    
    # Build parameters section
    parameters_md = ""
    if interface_info.get("parameters"):
        parameters_md = "\n## Parameters\n\n"
        for param in interface_info["parameters"]:
            param_name = param["name"]
            param_units = param.get("units", "")
            param_desc = param.get("description", "")
            
            # Add unit info to the type
            param_type = param_units if param_units else "string"
            
            # Only include description if it's not empty
            if param_desc.strip():
                parameters_md += f"""<ParamField path="{param_name}" type="{param_type}">
  {param_desc}
</ParamField>

"""
            else:
                parameters_md += f"""<ParamField path="{param_name}" type="{param_type}">
</ParamField>

"""

    # Build interface fields section (sub-interfaces)
    interfaces_md = ""
    if interface_info.get("interfaces"):
        interfaces_md = "\n## Interface Fields\n\n"
        for interface in interface_info["interfaces"]:
            interface_name_field = interface["name"]
            interface_desc = interface.get("description", "")
            interface_type = interface.get("interface_type", "Electrical")
            
            if interface.get("count", 1) > 1:
                interface_type = f"{interface_type}[{interface['count']}]"
            
            # Only include description if it's not empty
            if interface_desc.strip():
                interfaces_md += f"""<ParamField path="{interface_name_field}" type="{interface_type}">
  {interface_desc}
</ParamField>

"""
            else:
                interfaces_md += f"""<ParamField path="{interface_name_field}" type="{interface_type}">
</ParamField>

"""

    # Build properties section
    properties_md = ""
    if interface_info.get("properties"):
        properties_md = "\n## Properties\n\n"
        for prop in interface_info["properties"]:
            prop_name = prop["name"]
            prop_desc = prop.get("docstring", "") or ""
            
            # Only include description if it's not empty
            if prop_desc and prop_desc.strip():
                properties_md += f"""<ParamField path="{prop_name}" type="property" readonly>
  {prop_desc}
</ParamField>

"""
            else:
                properties_md += f"""<ParamField path="{prop_name}" type="property" readonly>
</ParamField>

"""

    # Build traits section
    traits_md = ""
    if interface_info.get("traits"):
        traits_md = "\n## Traits\n\n"
        for trait in interface_info["traits"]:
            trait_name = trait["name"]
            trait_desc = get_trait_description(trait_name)
            
            # Get the actual trait class name for proper linking
            trait_url_name = trait_name.replace("_", "-")
            trait_link = f"/atopile/api-reference/traits/{trait_url_name}"
            
            if trait_desc.strip():
                traits_md += f"[{trait_name}]({trait_link})\n\n{trait_desc}\n\n"
            else:
                traits_md += f"[{trait_name}]({trait_link})\n\n"

    return f"""---
title: "{interface_name}"
icon: "right-left"
description: "{description}"
---
{parameters_md}{interfaces_md}{properties_md}{traits_md}"""

def generate_trait_markdown(trait_name: str) -> str:
    """Generate markdown for a trait."""
    description = get_trait_description(trait_name)
    
    # Only use description if we actually found a docstring
    if not description:
        description = ""
    
    return f"""---
title: "{trait_name}"
#icon: "fingerprint"
description: "{description}"
---
"""

def get_all_library_files() -> Dict[str, List[str]]:
    """Get all component, interface, and trait files from the library based on direct inheritance."""
    if not LIBRARY_PATH.exists():
        print(f"Library path not found: {LIBRARY_PATH}")
        return {"components": [], "interfaces": [], "traits": []}
    
    components = []
    interfaces = []
    traits = []
    
    # Get all Python files
    for py_file in LIBRARY_PATH.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Find class definitions and check direct inheritance
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                    
                    # Get direct base classes (only immediate parents)
                    direct_bases = []
                    for base in node.bases:
                        if isinstance(base, ast.Attribute):
                            # Handle cases like Module.TraitT
                            if isinstance(base.value, ast.Name):
                                direct_bases.append(f"{base.value.id}.{base.attr}")
                            else:
                                direct_bases.append(base.attr)
                        elif isinstance(base, ast.Name):
                            # Handle cases like Module, ModuleInterface
                            direct_bases.append(base.id)
                        elif isinstance(base, ast.Call):
                            # Handle cases like Module.TraitT.decless(), F.SomeClass.impl()
                            if isinstance(base.func, ast.Attribute):
                                if isinstance(base.func.value, ast.Attribute):
                                    # Handle Module.TraitT.decless()
                                    if isinstance(base.func.value.value, ast.Name):
                                        full_name = f"{base.func.value.value.id}.{base.func.value.attr}.{base.func.attr}"
                                        direct_bases.append(full_name)
                                        # Also add the parent class for categorization
                                        direct_bases.append(f"{base.func.value.value.id}.{base.func.value.attr}")
                    
                    # Categorize based on DIRECT inheritance only
                    if py_file.stem in functional_trait_names:
                        if class_name not in traits:
                            traits.append(class_name)
                    elif "Module" in direct_bases and "Module.TraitT" not in direct_bases:
                        # Must inherit from Module but NOT Module.TraitT
                        if class_name not in components:
                            components.append(class_name)
                    elif "ModuleInterface" in direct_bases:
                        if class_name not in interfaces:
                            interfaces.append(class_name)
                            
        except Exception as e:
            print(f"Error analyzing {py_file.name}: {e}")
    
    return {
        "components": sorted(components),
        "interfaces": sorted(interfaces),
        "traits": sorted(traits)
    }

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
    print("Clearing existing documentation files...")
    clear_existing_docs()
    
    # Extract global attributes once for all components
    print("Extracting Global Attributes...")
    global_attributes, global_attributes_docstring = extract_global_attributes()
    print(f"Found {len(global_attributes)} global attributes")
    
    # Get all library files
    library_files = get_all_library_files()
    base_path = Path(__file__).parent / "atopile" / "api-reference"
    
    # Generate component pages
    components_path = base_path / "components"
    components_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGenerating {len(library_files['components'])} component pages...")
    for component_name in library_files['components']:  # Remove limit [:10]
        print(f"  Processing {component_name}...")
        component_info = extract_component_info(component_name)
        
        if component_info:
            file_path = components_path / f"{component_name.lower()}.mdx"
            content = generate_component_markdown(component_info, global_attributes, global_attributes_docstring)
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            print(f"    Created {file_path}")
        else:
            print(f"    Failed to extract info for {component_name}")
    
    # # Generate interface pages
    # interfaces_path = base_path / "interfaces"
    # interfaces_path.mkdir(parents=True, exist_ok=True)
    
    # print(f"\nGenerating {len(library_files['interfaces'])} interface pages...")
    # for interface_name in library_files['interfaces']:  # Remove limit [:10]
    #     print(f"  Processing {interface_name}...")
    #     file_path = interfaces_path / f"{interface_name.lower().replace('_', '-')}.mdx"
    #     content = generate_interface_markdown(interface_name)
        
    #     with open(file_path, 'w') as f:
    #         f.write(content)
        
    #     print(f"    Created {file_path}")
    
    # Generate trait pages  
    traits_path = base_path / "traits"
    traits_path.mkdir(parents=True, exist_ok=True)

    # Manually select functional traits
    functional_traits = [trait for trait in library_files['traits'] if trait in functional_trait_names]
    
    print(f"\nGenerating {len(functional_traits)} trait pages...")
    for trait_name in functional_traits:  # Remove limit [:10]
        print(f"  Processing {trait_name}...")
        file_path = traits_path / f"{trait_name.replace('_', '-')}.mdx"
        content = generate_trait_markdown(trait_name)
        
        with open(file_path, 'w') as f:
            f.write(content)
            
        print(f"    Created {file_path}")

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
    
    print(f"\n✅ Updated navigation in docs.json")
    print(f"📁 Scanned: {base_path}")
    print(f"🔄 Only existing .mdx files are included in navigation")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--update-nav-only":
            print("Updating navigation in docs.json...")
            update_navigation()
            print("\n✅ Navigation update complete!")
        elif sys.argv[1] == "--clear-only":
            print("Clearing existing documentation files...")
            clear_existing_docs()
            print("✅ Clear complete!")
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python generate-all-docs.py                  # Generate all docs + update navigation")
            print("  python generate-all-docs.py --update-nav-only # Update navigation only")
            print("  python generate-all-docs.py --clear-only      # Clear existing docs only")
            print("  python generate-all-docs.py --help            # Show this help")
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for available options")
    else:
        print("Generating atopile library documentation...")
        generate_all_docs()
        update_navigation()
        print("\n✅ Documentation generation complete!")
        print("📖 View your docs at: http://localhost:3001") 