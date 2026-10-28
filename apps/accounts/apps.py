import sys

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _crear_admin_inicial(sender, **kwargs):
    if sys.argv[1:2] == ["test"]:
        return
    from django.core.management import call_command

    call_command("crear_admin_inicial")


class AccountsConfig(AppConfig):
    name = 'apps.accounts'

    def ready(self):
        post_migrate.connect(
            _crear_admin_inicial,
            sender=self,
            dispatch_uid="accounts.crear_admin_inicial",
        )