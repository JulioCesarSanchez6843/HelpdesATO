import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from apps.tickets import cierre_automatico, emails


class Command(BaseCommand):
    help = "Se queda corriendo: envía la cola de correos y cierra tickets vencidos según la hora del servidor."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cada-correos",
            type=int,
            default=10,
            help="Segundos entre revisiones de la cola de correos.",
        )
        parser.add_argument(
            "--cada-cierre",
            type=int,
            default=3600,
            help="Segundos entre revisiones de tickets vencidos.",
        )

    def marca(self):
        return timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")

    def tarea_correos(self):
        enviados, fallidos = emails.procesar_pendientes()
        emails.limpiar_enviados()
        if enviados or fallidos:
            self.stdout.write(
                f"[{self.marca()}] Correos enviados: {enviados}. Con error: {fallidos}."
            )

    def tarea_cierre(self):
        resultado = cierre_automatico.ejecutar()
        if not resultado["activo"]:
            return
        if resultado["cerrados"] or resultado["recordatorios"]:
            self.stdout.write(
                f"[{self.marca()}] Tickets cerrados: {resultado['cerrados']}. "
                f"Recordatorios: {resultado['recordatorios']}."
            )
        for error in resultado["errores"]:
            self.stderr.write(f"[{self.marca()}] {error}")

    def handle(self, *args, **options):
        cada_correos = max(options["cada_correos"], 1)
        cada_cierre = max(options["cada_cierre"], 60)

        self.stdout.write(
            f"[{self.marca()}] Tareas en marcha. Correos cada {cada_correos}s, "
            f"cierre de tickets cada {cada_cierre}s. Ctrl + C para detener."
        )

        proxima_correos = 0.0
        proxima_cierre = 0.0

        try:
            while True:
                close_old_connections()
                ahora = time.monotonic()

                if ahora >= proxima_correos:
                    try:
                        self.tarea_correos()
                    except Exception as error:
                        self.stderr.write(f"[{self.marca()}] Error en correos: {error}")
                    proxima_correos = time.monotonic() + cada_correos

                if ahora >= proxima_cierre:
                    try:
                        self.tarea_cierre()
                    except Exception as error:
                        self.stderr.write(f"[{self.marca()}] Error en cierre: {error}")
                    proxima_cierre = time.monotonic() + cada_cierre

                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("Detenido.")