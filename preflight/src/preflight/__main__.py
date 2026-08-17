"""Enable `python -m preflight ...` as an alias for the `preflight` console script."""

import sys

from .cli import main

sys.exit(main())
