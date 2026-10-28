import time

from django.core.management.base import BaseCommand

from apps.tickets import emails


class Command(BaseCommand):
    help = "Envía los correos pendientes de la cola."

    def add_arguments(self, parser):
        parser.add_argument(
            "--continuo",
            action="store_true",
            help="Se queda corriendo y revisa la cola cada cierto tiempo.",
        )
        parser.add_argument(
            "--cada",
            type=int,
            default=10,
            help="Segundos entre revisiones en modo continuo.",
        )

    def handle(self, *args, **options):
        if not options["continuo"]:
            enviados, fallidos = emails.procesar_pendientes()
            emails.limpiar_enviados()
            self.stdout.write(f"Enviados: {enviados}. Con error: {fallidos}.")
            return

        self.stdout.write("Procesando la cola de correos. Ctrl + C para detener.")
        try:
            while True:
                try:
                    enviados, fallidos = emails.procesar_pendientes()
                    if enviados or fallidos:
                        self.stdout.write(
                            f"Enviados: {enviados}. Con error: {fallidos}."
                        )
                    emails.limpiar_enviados()
                except Exception as error:
                    self.stderr.write(f"Error al procesar la cola: {error}")
                time.sleep(options["cada"])
        except KeyboardInterrupt:
            self.stdout.write("Detenido.")