from faebryk.core.node import Node
from faebryk.core.module import Module
from faebryk.core.moduleinterface import ModuleInterface
from faebryk.core.trait import Trait
from faebryk.core.parameter import Parameter
from atopile.attributes import GlobalAttributes
from faebryk.library.can_bridge_by_name import can_bridge_by_name
from faebryk.library.MultiCapacitor import MultiCapacitor
import inspect
import ast
import os
from pathlib import Path

from atopile.mcp.tools.library import _get_library_nodes

LIBRARY_PATH = Path(__file__).parent.parent / "atopile" / "src" / "faebryk" / "library"
# nodes = _get_library_nodes(t=ModuleInterface)
# for node in nodes:
#     print(node.name)

m = MultiCapacitor.__new__(MultiCapacitor)
m.__init__
# m = MultiCapacitor(2)
print(m.get_children(direct_only=True, types=ModuleInterface))

# print("\n=== Reading source file directly ===")
# # Parse the AST
# # Path to the trait file in the atopile source
# trait_file_path = LIBRARY_PATH / f"{can_bridge_by_name.__name__}.py"
# if not trait_file_path.exists():
#     exit()
# try:
#     with open(trait_file_path, "r", encoding="utf-8") as f:
#         content = f.read()
#     tree = ast.parse(content)

#     # Find the class and its __init__ method
#     for node in ast.walk(tree):
#         if isinstance(node, ast.ClassDef) and node.name == "can_bridge_by_name":
#             print(f"Found class {node.name}")
#             for item in node.body:
#                 if isinstance(item, ast.FunctionDef) and item.name == "__init__":
#                     print(f"Arguments: {[arg.arg for arg in item.args.args]}")

#                     # Get argument types and defaults
#                     for i, arg in enumerate(item.args.args):
#                         if arg.arg != "self":
#                             print(f"Parameter: {arg.arg}")

#                             # Get type annotation
#                             if arg.annotation:
#                                 if isinstance(arg.annotation, ast.Name):
#                                     print(f"  Type: {arg.annotation.id}")
#                                 elif isinstance(arg.annotation, ast.Constant):
#                                     print(f"  Type: {arg.annotation.value}")
#                                 else:
#                                     print(f"  Type: {ast.dump(arg.annotation)}")
#                             else:
#                                 print(f"  Type: None")

#                             # Get default value
#                             defaults_start = len(item.args.args) - len(
#                                 item.args.defaults
#                             )
#                             if i >= defaults_start:
#                                 default_idx = i - defaults_start
#                                 default = item.args.defaults[default_idx]
#                                 if isinstance(default, ast.Constant):
#                                     print(f"  Default: {repr(default.value)}")
#                                 else:
#                                     print(f"  Default: {ast.dump(default)}")
#                             else:
#                                 print(f"  Default: No default")
#                             print()
#                     break
#             break
# except Exception as e:
#     print(f"Error: {e}")
