#!/usr/bin/env python3
"""
Generate markdown documentation for all atopile library components, interfaces, and traits.
Uses AST parsing to extract real docstrings and information from source files.
"""

import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import importlib
import inspect
import textwrap

import faebryk.library._F as F


from faebryk.core.node import Node
from faebryk.core.module import Module
from faebryk.core.moduleinterface import ModuleInterface
from faebryk.core.trait import Trait
from faebryk.core.parameter import Parameter
from atopile.attributes import GlobalAttributes

from atopile.mcp.tools.library import _get_library_nodes

# Base path to the atopile library source
LIBRARY_PATH = Path(__file__).parent.parent / "atopile" / "src" / "faebryk" / "library"
ATTRIBUTES_PATH = (
    Path(__file__).parent.parent / "atopile" / "src" / "atopile" / "attributes.py"
)
BASE_DOC_PATH = Path(__file__).parent / "atopile" / "api-reference"

doc_types = {"component": Module, "interface": ModuleInterface, "trait": Trait}

icons = {"component": "microchip", "interface": "right-left", "trait": "right-left"}

data_types = {"parameter": Parameter, "interface": ModuleInterface, "trait": Trait}

# Not all traits are functional or reasonable to expose to users
functional_trait_names = [
    "can_bridge",
    "can_bridge_by_name",
    "has_single_electric_reference",
    "is_pickable",
    "requires_pulls",
]
excluded_attributes = {
    "datasheet_url",
    "designator_prefix",
    "footprint",
    "suggest_net_name",
}


# TODO: this is a hack, fix once types are first class in graph
def generate_dummy_value(param_type, param_name: str):
    """Generate appropriate dummy values based on parameter type annotation."""
    import typing

    # Handle actual type objects
    if param_type is int:
        return 1
    elif param_type is str:
        return "dummy"
    elif param_type is bool:
        # Special cases for common boolean parameter names
        if "closed" in param_name.lower():
            return False
        return True
    elif param_type is float:
        return 1.0
    elif param_type is list:
        return ["dummy"]
    elif param_type is dict:
        return {}
    elif param_type is tuple:
        return ("dummy",)
    elif hasattr(param_type, "__origin__"):
        # Handle generic types like Callable, etc.
        from typing import get_origin, get_args

        origin = get_origin(param_type)
        args = get_args(param_type)

        if param_type.__origin__ is typing.Union:
            # For Union types, try the first non-None type
            type_args = param_type.__args__
            for arg in type_args:
                if arg is not type(None):
                    return generate_dummy_value(arg, param_name)
        elif origin is list or origin is typing.List:
            # For List[T], return a list with one dummy element
            if args:
                dummy_element = generate_dummy_value(args[0], param_name)
                return [dummy_element] if dummy_element is not None else ["dummy"]
            return ["dummy"]
        elif origin is dict or origin is typing.Dict:
            return {}
        elif origin is tuple or origin is typing.Tuple:
            if args:
                return tuple(generate_dummy_value(arg, param_name) for arg in args)
            return ("dummy",)
        elif origin is typing.Callable:
            # For Callable types, return a simple lambda
            return lambda: None
        return None
    else:
        # For custom types or complex types, try to instantiate with common patterns
        try:
            # Try no-argument constructor first
            if hasattr(param_type, "__call__"):
                return param_type()
        except:
            try:
                # Try with a single string argument (common pattern)
                if hasattr(param_type, "__call__"):
                    return param_type("dummy")
            except:
                pass

    # Fallback for specific parameter names
    if "factory" in param_name.lower():
        # For factory parameters, return a simple lambda
        return lambda: None
    elif "list" in param_name.lower() or "items" in param_name.lower():
        return ["dummy"]
    elif "count" in param_name.lower() or "num" in param_name.lower():
        return 1

    return None


def create_library_node(name: str, t: type[Node] = Node) -> Optional[Node]:
    try:
        if (
            name not in F.__dict__
        ):  # name of the module to be searched in the imports of the internal namespace __dict__ of _F imports
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

        # Try to instantiate with no arguments first
        try:
            node = module_class()
            return node
        except TypeError as init_error:
            # If that fails, try to get the original signature and generate arguments
            if hasattr(module_class, "__original_init__"):
                try:
                    sig = inspect.signature(module_class.__original_init__)
                    args = []
                    kwargs = {}

                    for param_name, param in sig.parameters.items():
                        if param_name == "self":
                            continue

                        # Generate dummy value based on type annotation
                        dummy_value = generate_dummy_value(param.annotation, param_name)

                        if param.default != inspect.Parameter.empty:
                            # Has default, skip it
                            continue
                        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
                            kwargs[param_name] = dummy_value
                        else:
                            args.append(dummy_value)

                    node = module_class(*args, **kwargs)
                    return node
                except Exception as sig_error:
                    raise ValueError(
                        f"Failed to instantiate {name} with generated args: {sig_error}"
                    )
            else:
                # No original init available, re-raise the original error
                raise init_error

    except Exception as e:
        print(f"Error creating library node {name}: {e}")
        return None


def get_global_attributes():
    props = []
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
            props.append({"name": name, "type": arg_type, "doc": doc})
    return props


def get_init_args(node_name: str) -> list:
    """Get descriptive text for traits from their actual source files."""
    init_args = []

    # Path to the trait file in the atopile source
    trait_file_path = LIBRARY_PATH / f"{node_name}.py"
    if not trait_file_path.exists():
        return init_args
    try:
        content = trait_file_path.read_text()
        tree = ast.parse(content)
        # Find the class definition and extract its docstring
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == node_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        # Get argument types and defaults
                        for i, arg in enumerate(item.args.args):
                            if arg.arg != "self":
                                arg_info = {"input_name": arg.arg}

                                # Get type annotation - use original source text
                                if arg.annotation:
                                    try:
                                        arg_info["input_type"] = ast.unparse(
                                            arg.annotation
                                        )
                                    except Exception:
                                        arg_info["input_type"] = "Unknown"
                                else:
                                    arg_info["input_type"] = ""

                                # Get default value - use original source text
                                defaults_start = len(item.args.args) - len(
                                    item.args.defaults
                                )
                                if i >= defaults_start:
                                    default_idx = i - defaults_start
                                    default = item.args.defaults[default_idx]
                                    #  if isinstance(default, ast.Constant):
                                    #     arg_info["default"] = str(default.value)
                                    # else:
                                    #     arg_info["default"] = ast.dump(default)
                                    try:
                                        arg_info["default"] = ast.unparse(default)
                                    except Exception:
                                        arg_info["default"] = "Unknown"
                                else:
                                    arg_info["default"] = ""

                                init_args.append(arg_info)
                        break
        return init_args

    except Exception as e:
        print(f"Error reading trait file {node_name}.py: {e}")
        return init_args


def append_mkdn_init_arg(arg: dict) -> str:
    # if arg.get("default", "").strip():
    # return f"<ParamField path='{arg['input_name']}' type='{arg['input_type']}'>\n\n{arg['default']}\n</ParamField>\n\n"
    # else:
    return f"<ParamField path='{arg['input_name']}' type='{arg['input_type'].replace("'", '"')}'>\n\n</ParamField>\n\n"


def append_mkdn_parameter(param: Parameter) -> str:
    param_name = param.get_name()
    param_units = str(param.units) if param.units else "string"
    param_desc = param.__doc__ or ""
    # param_type = type(param).__name__
    if param_desc.strip():
        return f"<ParamField path='{param_name}' type='{param_units}'>\n\n{param_desc}\n</ParamField>\n\n"
    else:
        return (
            f"<ParamField path='{param_name}' type='{param_units}'>\n</ParamField>\n\n"
        )


def append_mkdn_attributes(param) -> str:
    param_name = param["name"]
    param_type = param["type"].__name__
    param_desc = param["doc"]
    if param_desc:
        return f"<ParamField path='{param_name}' type='{param_type}'>\n\n{param_desc}\n</ParamField>\n\n"
    else:
        return (
            f"<ParamField path='{param_name}' type='{param_type}'>\n</ParamField>\n\n"
        )


# Generate one parameter line in a page
def append_mkdn_interface(param: ModuleInterface) -> str:
    param_name = param.get_name()
    param_desc = ""  # param.__doc__ or ""
    if_type = type(param).__name__

    # Only include description if it's not empty
    if param_desc.strip():
        return f"<ParamField path='{param_name}' type='{if_type}'>\n\n{param_desc}\n</ParamField>\n\n"
    else:
        return f"<ParamField path='{param_name}' type='{if_type}'>\n</ParamField>\n\n"


# Generate one trait line in a page
def append_mkdn_trait(trait: Node) -> str:
    trait_name = trait.__class__.__name__
    trait_desc = trait.__doc__ or ""

    # Get the actual trait class name for proper linking
    trait_url_name = trait_name.replace("_", "-")
    trait_link = f"/atopile/api-reference/traits/{trait_url_name}"
    traits_m = ""
    if trait_name in functional_trait_names:
        # traits_m += f"[{trait_name}]({trait_link})\n\n"
        traits_m += f"**{trait_name}**\n\n"
    else:
        pass
    if trait_desc.strip():
        traits_m += f"{trait_desc}\n\n"
    return traits_m


def append_mkdn_usage_example(usage_example: F.has_usage_example) -> str:
    return f"<RequestExample>\n```{usage_example._language} Basic Usage\n{textwrap.dedent(usage_example._example).strip()}\n```\n</RequestExample>"


# Generate one page of documentation
def generate_node_markdown(
    node_data: Dict[str, Any],
    icon_name: str,
    global_attributes: List[Dict[str, Any]],
    global_attributes_docstring: Optional[str],
) -> str:
    """Generate the complete markdown documentation for a module."""

    node_name = node_data["name"]

    # Build init args section
    init_args_md = ""
    if node_data.get("init_args"):
        init_args_md = "\n## Init Args\n\n"
        for arg in node_data["init_args"]:
            if len(arg) > 0:
                init_args_md += append_mkdn_init_arg(arg)

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
    if len(node_data.get("traits", [])) > 0:
        traits_md = "\n## Traits\n\n"
        for trait in node_data["traits"]:
            traits_md += append_mkdn_trait(trait)

    # Build usage example section
    usage_example_md = ""
    if node_data.get("usage_example"):
        usage_example_md = ""
        for usage_example in node_data["usage_example"]:
            usage_example_md += append_mkdn_usage_example(usage_example)

    # Build global attributes section
    global_attributes_md = ""
    if global_attributes and node_data.get("type", "") != Trait:
        # Filter out specific attributes that shouldn't be in docs
        filtered_attributes = [
            attr
            for attr in global_attributes
            if attr["name"] not in excluded_attributes
        ]
        if filtered_attributes:  # Only create section if there are attributes to show
            global_attributes_md = (
                f"\n## Global Attributes\n\n{GlobalAttributes.__doc__}"
            )
            # Add class docstring if available
            if global_attributes_docstring and global_attributes_docstring.strip():
                global_attributes_md += f"{global_attributes_docstring.strip()}\n\n"
            for attr in filtered_attributes:
                attr["description"] = attr.get("docstring", "")
                global_attributes_md += append_mkdn_attributes(attr)

    # module description
    description = node_data.get("docstring", "")

    if len(node_name) > 20:
        icon_name = ""

    # Generate the complete markdown
    markdown = f'---\n\ntitle: "{node_name}"\nicon: {icon_name}\ndescription: "{description}"\n---\n\n{init_args_md}{parameters_md}{interfaces_md}{traits_md}{global_attributes_md}{usage_example_md}'

    return markdown


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
        base_file_path = BASE_DOC_PATH / f"{doc_name}s"
        base_file_path.mkdir(parents=True, exist_ok=True)
        for node_info in node_info_list:
            if node_type == Trait and node_info.name not in functional_trait_names:
                continue  # Only list functional trait names for now
            node = create_library_node(node_info.name, t=node_type)
            if node:
                node_data = {}
                node_data["type"] = node_type
                node_data["name"] = node_info.name
                node_data["docstring"] = node_info.docstring
                node_data["init_args"] = get_init_args(node_info.name)
                node_data["parameters"] = node.get_children(
                    direct_only=True, types=Parameter, include_root=False
                )
                node_data["interfaces"] = node.get_children(
                    direct_only=True, types=ModuleInterface, include_root=False
                )
                node_data["traits"] = node.get_children(
                    direct_only=True, types=Trait, include_root=False
                )
                node_data["traits"] = [
                    n
                    for n in node_data["traits"]
                    if n.__class__.__name__ in functional_trait_names
                ]
                node_data["modules"] = node.get_children(
                    direct_only=True, types=Module, include_root=False
                )
                node_data["usage_example"] = node.get_children(
                    direct_only=True, types=F.has_usage_example, include_root=False
                )
                doc_file_path = base_file_path / f"{node_info.name.lower()}.mdx"
                # doc_file_path.mkdir(parents=True, exist_ok=True)
                content = generate_node_markdown(
                    node_data, icons[doc_name], global_attributes, None
                )
                with open(doc_file_path, "w") as f:
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
                                    relative_path = page_path.replace(
                                        "atopile/api-reference/", ""
                                    )
                                    actual_file_path = (
                                        base_path / f"{relative_path}.mdx"
                                    )
                                    if not actual_file_path.exists():
                                        current_missing_files.append(page_path)

    if current_missing_files:
        print(
            f"🗑️  Found {len(current_missing_files)} missing files in current docs.json:"
        )
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
                components_pages.append(
                    f"atopile/api-reference/components/{file_path.stem}"
                )

    # Get interfaces pages - only include files that actually exist
    interfaces_pages = []
    interfaces_path = base_path / "interfaces"
    if interfaces_path.exists():
        for file_path in sorted(interfaces_path.glob("*.mdx")):
            if file_path.is_file() and file_path.exists():
                interfaces_pages.append(
                    f"atopile/api-reference/interfaces/{file_path.stem}"
                )

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
                        {"group": "Components", "pages": components_pages},
                        {"group": "Interfaces", "pages": interfaces_pages},
                        {"group": "Traits", "pages": traits_pages},
                    ]

                    print("Updated Library Reference section:")
                    print(
                        f"  Components: {old_component_count} → {len(components_pages)} pages"
                    )
                    print(
                        f"  Interfaces: {old_interface_count} → {len(interfaces_pages)} pages"
                    )
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
    with open(docs_json_path, "w") as f:
        json.dump(docs_config, f, indent=2)

    print("\n✅ Updated navigation in docs.json")
    print(f"📁 Scanned: {base_path}")
    print("🔄 Only existing .mdx files are included in navigation")


if __name__ == "__main__":
    generate_all_docs()
    update_navigation()
