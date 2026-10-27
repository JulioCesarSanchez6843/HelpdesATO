from django.core.management.base import BaseCommand, CommandError

from apps.tickets import cierre_automatico


class Command(BaseCommand):
    help = "Cierra los tickets vencidos en «Por confirmar» y envía los recordatorios previos, según la Configuración del sistema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=None,
            help="Usa estos días en lugar de la configuración (implica --forzar).",
        )
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Corre aunque el cierre automático esté desactivado en la configuración.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra qué se haría, sin cambiar nada.",
        )

    def handle(self, *args, **options):
        dias = options["dias"]
        if dias is not None and dias < 1:
            raise CommandError("--dias debe ser 1 o mayor.")

        resultado = cierre_automatico.ejecutar(
            dias=dias,
            forzar=options["forzar"] or dias is not None,
            dry_run=options["dry_run"],
        )

        if not resultado["activo"]:
            self.stdout.write(
                "El cierre automático está desactivado en Configuración. No se hizo nada."
            )
            return

        if options["dry_run"]:
            self.stdout.write(
                f"Se cerrarían {len(resultado['a_cerrar'])} ticket(s): {resultado['a_cerrar']}"
            )
            self.stdout.write(
                f"Se avisaría a {len(resultado['a_recordar'])} usuario(s): {resultado['a_recordar']}"
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Tickets cerrados: {resultado['cerrados']}. "
                f"Recordatorios enviados: {resultado['recordatorios']}."
            )
        )
        if resultado["errores"]:
            for error in resultado["errores"]:
                self.stderr.write(error)
            raise CommandError(f"Tickets con error: {len(resultado['errores'])}")