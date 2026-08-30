"""
specshift - OpenAPI ve Swagger sozlesmelerindeki degisiklikleri tespit eden,
siniflandiran ve isteğe bagli olarak yapay zeka ile ozetleyen arac.
"""

from specshift.differ import diff_specs
from specshift.models import Change, Severity, ChangeType, DiffResult
from specshift.spec_loader import load_spec

__version__ = "1.0.0"

__all__ = [
    "diff_specs",
    "load_spec",
    "Change",
    "Severity",
    "ChangeType",
    "DiffResult",
    "__version__",
]
