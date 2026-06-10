import sys
import os
import contextlib

# Caches to store the sys.modules state for each version
_custom_modules = {}
_standard_modules = {}

@contextlib.contextmanager
def use_custom_transformers():
    global _custom_modules, _standard_modules
    
    # Check what transformers modules are currently in sys.modules
    current_transformers = {k: v for k, v in list(sys.modules.items()) if k == "transformers" or k.startswith("transformers.")}
    
    # Detect if currently loaded version is custom
    is_currently_custom = False
    if "transformers" in sys.modules:
        tf_mod = sys.modules["transformers"]
        if hasattr(tf_mod, "__file__") and tf_mod.__file__ and "custom_transformers" in tf_mod.__file__:
            is_currently_custom = True
            
    if not is_currently_custom:
        # Save standard modules
        _standard_modules = current_transformers
        # Remove them from active sys.modules
        for k in current_transformers:
            sys.modules.pop(k, None)
        # Restore custom modules if any exist
        for k, v in _custom_modules.items():
            sys.modules[k] = v
            
        custom_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "custom_transformers")
        sys.path.insert(0, custom_path)
        try:
            yield
        finally:
            # Save custom modules back
            _custom_modules = {k: v for k, v in list(sys.modules.items()) if k == "transformers" or k.startswith("transformers.")}
            # Remove them from active sys.modules
            for k in _custom_modules:
                sys.modules.pop(k, None)
            if custom_path in sys.path:
                sys.path.remove(custom_path)
            # Restore standard modules
            for k, v in _standard_modules.items():
                sys.modules[k] = v
    else:
        yield

@contextlib.contextmanager
def use_standard_transformers():
    global _custom_modules, _standard_modules
    
    current_transformers = {k: v for k, v in list(sys.modules.items()) if k == "transformers" or k.startswith("transformers.")}
    
    is_currently_custom = False
    if "transformers" in sys.modules:
        tf_mod = sys.modules["transformers"]
        if hasattr(tf_mod, "__file__") and tf_mod.__file__ and "custom_transformers" in tf_mod.__file__:
            is_currently_custom = True
            
    if is_currently_custom:
        # Save custom modules
        _custom_modules = current_transformers
        # Remove them from active sys.modules
        for k in current_transformers:
            sys.modules.pop(k, None)
        # Restore standard modules if any exist
        for k, v in _standard_modules.items():
            sys.modules[k] = v
            
        custom_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "custom_transformers")
        removed_from_path = False
        if custom_path in sys.path:
            sys.path.remove(custom_path)
            removed_from_path = True
            
        try:
            yield
        finally:
            # Save standard modules back
            _standard_modules = {k: v for k, v in list(sys.modules.items()) if k == "transformers" or k.startswith("transformers.")}
            # Remove them from active sys.modules
            for k in _standard_modules:
                sys.modules.pop(k, None)
            if removed_from_path:
                sys.path.insert(0, custom_path)
            # Restore custom modules
            for k, v in _custom_modules.items():
                sys.modules[k] = v
    else:
        yield
