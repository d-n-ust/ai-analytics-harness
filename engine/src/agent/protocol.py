"""Import shim: the module moved to core/ (refactor last mile). The public path stays stable
for every experiment script and test; the implementation lives in the pure layer."""
from .core.protocol import *                                                        # noqa: F401,F403
