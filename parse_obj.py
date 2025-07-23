from pathlib import Path
from faebryk.core.node import Node
from faebryk.core.cpp import Graph
from faebryk.core.module import Module
from faebryk.core.moduleinterface import ModuleInterface
from faebryk.core.trait import Trait
from faebryk.core.parameter import Parameter
from atopile.mcp.tools.library import _get_library_node, _get_library_nodes

def create_library_node(name: str, t: type[Node] = Node) -> Node:
    import faebryk.library._F as F

    if name not in F.__dict__: # name of the module to be searched in the imports of the internal namespace __dict__ of _F imports
        raise ValueError(f"Type {name} not found")

    m = F.__dict__[name]

    if not isinstance(m, type) or not issubclass(m, t):
        raise ValueError(f"Type {name} is not a valid {t.__name__}")

    # get file of module
    file = m.__module__
    if file is None:
        raise ValueError(f"Type {name} is not part of a module")

    # import the module to get its file path
    import importlib

    module = importlib.import_module(file)

    if module.__file__ is None:
        raise ValueError(f"Type {name} has no file")

    # Get the class from the module and instantiate it
    module_class = getattr(module, name)
    if not isinstance(module_class, type):
        raise ValueError(f"{name} is not a class")
    
    # Instantiate the class object
    module_node = module_class()

    return module_node

all_nodes = _get_library_nodes(Module)
node_info = _get_library_node("Mounting_Hole")
# print(node_info)

node = create_library_node("Mounting_Hole")

print(node.__class__.__name__)

# print(node.get_children(direct_only=False, types=Trait, include_root=False))

# from faebryk.library._F import Mounting_Hole
# import importlib

# mod = importlib.import_module(Mounting_Hole.__module__)
# print(vars(mod))