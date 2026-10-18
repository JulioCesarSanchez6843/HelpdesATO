"""Configuración para desarrollo local (tu máquina)."""
import sys

from .base import *

DEBUG = True

INSTALLED_APPS += [
    "django.contrib.admindocs",
]

AUTH_PASSWORD_VALIDATORS = []

if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]