"""
Settings package for war_site project.
"""
import os
from decouple import config

# Determine which settings to use
ENVIRONMENT = config('ENVIRONMENT', default='development')

if ENVIRONMENT == 'production':
    from .production import *
elif ENVIRONMENT == 'testing':
    from .testing import *
else:
    from .development import *