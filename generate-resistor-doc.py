#!/usr/bin/env python3
"""
Generate markdown documentation for the Resistor component specifically.
Simplified version for faster development iteration.
"""

import ast
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# Base path to the atopile library source
LIBRARY_PATH = Path("/Users/nicholaskrstevski/github/atopile/src/faebryk/library")
ATTRIBUTES_PATH = Path("/Users/nicholaskrstevski/github/atopile/src/atopile/attributes.py")

def extract_resistor_info() -> Optional[Dict[str, Any]]:
    """Extract detailed information from the Resistor.py file."""
    resistor_file = LIBRARY_PATH / "Resistor.py"
    
    if not resistor_file.exists():
        print(f"Resistor file not found: {resistor_file}")
        return None
    
    try:
        with open(resistor_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        # Find the Resistor class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "Resistor":
                resistor_info = {
                    "name": "Resistor",
                    "docstring": ast.get_docstring(node),
                    "parameters": [],
                    "traits": [],
                    "properties": [],
                    "interfaces": []
                }
                
                print(f"Found Resistor class with {len(node.body)} items")
                
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
                                    print(f"  Found field: {field_name} -> {field_info['type']}")
                                    if field_docstring:
                                        print(f"    With docstring: {field_docstring[:50]}...")
                                    if field_info["type"] == "parameter":
                                        resistor_info["parameters"].append(field_info)
                                    elif field_info["type"] == "interface":
                                        resistor_info["interfaces"].append(field_info)
                    
                    elif isinstance(item, ast.FunctionDef):
                        if item.name.startswith('__'):
                            continue
                        
                        func_info = {
                            "name": item.name,
                            "docstring": ast.get_docstring(item),
                            "decorator": get_function_decorator(item)
                        }
                        
                        print(f"  Found method: {item.name} (decorator: {func_info['decorator']})")
                        
                        # Categorize based on decorator and name
                        if func_info["decorator"] == "property":
                            resistor_info["properties"].append(func_info)
                        elif (func_info["decorator"] == "L.rt_field" and is_rt_field_returning_trait(item)) or item.name in ['pickable', 'can_bridge', 'simple_value_representation']:
                            resistor_info["traits"].append(func_info)
                
                return resistor_info
                
    except Exception as e:
        print(f"Error parsing Resistor file: {e}")
        return None

def analyze_field_assignment(node: ast.Assign, field_name: str, docstring: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Analyze a field assignment to determine its type and properties."""
    try:
        # Convert the AST node to string for analysis
        if hasattr(ast, 'unparse'):
            value_str = ast.unparse(node.value)
        else:
            value_str = str(node.value)
        
        print(f"    Analyzing field {field_name}: {value_str}")
        
        # Parameter fields (L.p_field)
        if 'L.p_field' in value_str:
            units = extract_units_from_assignment(value_str)
            return {
                "name": field_name,
                "type": "parameter",
                "units": units,
                "description": get_parameter_description(field_name, units, docstring)
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
        
        # Field fields
        elif 'L.f_field' in value_str:
            return {
                "name": field_name,
                "type": "trait_field",
                "description": f"Trait field: {field_name}"
            }
            
    except Exception as e:
        print(f"    Error analyzing field {field_name}: {e}")
    
    return None

def get_parameter_description(field_name: str, units: Optional[str], docstring: Optional[str] = None) -> str:
    """Get a descriptive explanation for a parameter from docstrings if available."""
    # Use docstring if provided, otherwise return empty string
    if docstring and docstring.strip():
        return docstring.strip()
    
    # Return empty string instead of generated descriptions
    return ""

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

def generate_resistor_markdown(resistor_info: Dict[str, Any]) -> str:
    """Generate the complete markdown documentation for Resistor."""
    
    # Build parameters section
    parameters_md = ""
    if resistor_info.get("parameters"):
        parameters_md = "\n## Parameters\n\n"
        for param in resistor_info["parameters"]:
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
    if resistor_info.get("interfaces"):
        interfaces_md = "\n## Interfaces\n\n"
        for interface in resistor_info["interfaces"]:
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
    if resistor_info.get("properties"):
        properties_md = "\n## Properties\n\n"
        for prop in resistor_info["properties"]:
            prop_name = prop["name"]
            prop_desc = prop.get("docstring", "")
            
            # Only include description if it's not empty
            if prop_desc.strip():
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
    if resistor_info.get("traits"):
        traits_md = "\n## Traits\n\n"
        for trait in resistor_info["traits"]:
            trait_name = trait["name"]
            trait_desc = get_trait_description(trait_name)
            
            # Get the actual trait class name for proper linking
            trait_class_name = get_trait_class_name(trait_name)
            trait_url_name = trait_class_name.replace("_", "-")
            trait_link = f"/atopile/api-reference/traits/{trait_url_name}"
            
            if trait_desc.strip():
                traits_md += f"""[{trait_name}]({trait_link})

{trait_desc}

"""
            else:
                traits_md += f"""[{trait_name}]({trait_link})

"""

    # Build global attributes section
    global_attributes_md = ""
    if resistor_info.get("global_attributes"):
        # Filter out specific attributes that shouldn't be in docs
        excluded_attributes = {"datasheet_url", "designator_prefix", "footprint", "suggest_net_name"}
        filtered_attributes = [attr for attr in resistor_info["global_attributes"] 
                              if attr["name"] not in excluded_attributes]
        
        if filtered_attributes:  # Only create section if there are attributes to show
            global_attributes_md = "\n## Global Attributes\n\n"
            
            # Add class docstring if available
            class_docstring = resistor_info.get("global_attributes_docstring")
            if class_docstring and class_docstring.strip():
                global_attributes_md += f"{class_docstring.strip()}\n\n"
            
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
    description = resistor_info.get("docstring") or ""
    
    # Generate the complete markdown
    markdown = f"""---
title: "Resistor"
icon: "microchip"
description: "{description}"
---

<RequestExample>
```ato Quick Example
import Resistor

module Example:
    r1 = new Resistor
    r1.resistance = 10kohm +/- 5%
    r1.max_power = 0.125W
    r1.max_voltage = 50V
```
</RequestExample>
{parameters_md}{interfaces_md}{properties_md}{traits_md}{global_attributes_md}
"""

    return markdown

def extract_global_attributes() -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Extract global attributes from the GlobalAttributes class."""
    attributes_file = ATTRIBUTES_PATH
    
    if not attributes_file.exists():
        print(f"GlobalAttributes file not found: {attributes_file}")
        return [], None
    
    try:
        with open(attributes_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        attributes = []
        class_docstring = None
        
        # Find the GlobalAttributes class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "GlobalAttributes":
                print(f"Found GlobalAttributes class with {len(node.body)} items")
                
                # Extract the class docstring
                class_docstring = ast.get_docstring(node)
                if class_docstring:
                    print(f"Found GlobalAttributes class docstring: {class_docstring[:100]}...")
                
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
                                    print(f"  Found attribute: {attr_name}")
                                    if attr_docstring:
                                        print(f"    With docstring: {attr_docstring[:50]}...")
                
                return attributes, class_docstring
                
    except Exception as e:
        print(f"Error parsing GlobalAttributes file: {e}")
        return [], None

def get_trait_class_name(trait_method_name: str) -> str:
    """Map trait method names to their actual BASE trait class names (not implementations)."""
    
    # Map trait method names to their actual BASE trait class names (not implementations)
    trait_class_mapping = {
        "pickable": "is_pickable",  # Base trait, not is_pickable_by_type
        "can_bridge": "can_bridge",  # Base trait, not can_bridge_defined
        "simple_value_representation": "has_simple_value_representation",  # Base trait, not implementations
        "single_electric_reference": "has_single_electric_reference",  # Base trait, not _defined
        "requires_pulls": "requires_pulls",
        "can_be_decoupled": "can_be_decoupled",
        "can_be_surge_protected": "can_be_surge_protected",  # Base trait, not _defined
        "has_datasheet": "has_datasheet",  # Base trait, not _defined
        "has_footprint": "has_footprint",  # Base trait, not _defined
        "has_designator": "has_designator",
        "has_designator_prefix": "has_designator_prefix",
        "has_reference": "has_reference",
        "is_optional": "is_optional",  # Base trait, not _defined
        "requires_external_usage": "requires_external_usage",
        "has_pcb_position": "has_pcb_position",  # Base trait, not _defined
        "has_pcb_layout": "has_pcb_layout",  # Base trait, not _defined
        "has_esphome_config": "has_esphome_config",  # Base trait, not _defined
        "can_specialize": "can_specialize",  # Base trait, not _defined
        "can_switch_power": "can_switch_power",  # Base trait, not _defined
        "has_overriden_name": "has_overriden_name",  # Base trait, not _defined
        "has_descriptive_properties": "has_descriptive_properties",  # Base trait, not _defined
        "is_surge_protected": "is_surge_protected",  # Base trait, not _defined
        "is_decoupled": "is_decoupled",
        "is_representable_by_single_value": "is_representable_by_single_value",  # Base trait, not _defined
        "is_esphome_bus": "is_esphome_bus",  # Base trait, not _defined
        "has_linked_pad": "has_linked_pad",  # Base trait, not _defined
        "has_single_connection": "has_single_connection",  # Base trait, not _impl
        "has_symbol_layout": "has_symbol_layout"  # Base trait, not _defined
    }
    
    return trait_class_mapping.get(trait_method_name, trait_method_name)

def get_trait_description(trait_name: str) -> str:
    """Get descriptive text for traits from their actual source files."""
    
    # Get the actual trait class name for file lookup
    actual_trait_name = get_trait_class_name(trait_name)
    
    # Path to the trait file in the atopile source  
    trait_file_path = LIBRARY_PATH / f"{actual_trait_name}.py"
    
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
        print(f"Error reading trait file {actual_trait_name}.py: {e}")
        return ""

def main():
    """Main function to generate Resistor documentation."""
    print("Extracting Resistor component information...")
    
    resistor_info = extract_resistor_info()
    if not resistor_info:
        print("Failed to extract Resistor information")
        return
    
    print(f"Found {len(resistor_info['parameters'])} parameters")
    print(f"Found {len(resistor_info['interfaces'])} interfaces")
    print(f"Found {len(resistor_info['properties'])} properties") 
    print(f"Found {len(resistor_info['traits'])} traits")
    
    # Extract global attributes
    print("\nExtracting Global Attributes...")
    global_attributes, global_attributes_docstring = extract_global_attributes()
    resistor_info["global_attributes"] = global_attributes
    resistor_info["global_attributes_docstring"] = global_attributes_docstring
    print(f"Found {len(global_attributes)} global attributes")
    
    # Generate the markdown
    markdown_content = generate_resistor_markdown(resistor_info)
    
    # Write to file
    output_file = Path(__file__).parent / "atopile" / "api-reference" / "components" / "resistor.mdx"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write(markdown_content)
    
    print(f"\n✅ Generated Resistor documentation: {output_file}")
    print("📖 View at: http://localhost:3001/atopile/api-reference/components/resistor")

if __name__ == "__main__":
    main() 