import json
import re
from io import BytesIO, StringIO
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail.backends import locmem
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import Usuario
from apps.catalog.models import Area, Categoria, Sucursal

from . import emails
from .models import AdjuntoTicket, Historial, Notificacion, Ticket


PASSWORD = "pw-segura-123"


def imagen(nombre="foto.jpg", tamano=(40, 30), formato="JPEG", color="red"):
    buffer = BytesIO()
    Image.new("RGB", tamano, color).save(buffer, format=formato)
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type=f"image/{formato.lower()}")


class BaseTicketsTest(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Contabilidad")
        self.categoria = Categoria.objects.create(nombre="Red")
        self.sucursal = Sucursal.objects.create(nombre="Central")

        self.admin = Usuario.objects.create_user(
            "admin@t.com", "Admin", PASSWORD, rol=Usuario.Rol.SUPERADMIN, area=self.area
        )
        self.admin2 = Usuario.objects.create_user(
            "admin2@t.com", "Admin Dos", PASSWORD, rol=Usuario.Rol.SUPERADMIN, area=self.area
        )
        self.u1 = Usuario.objects.create_user(
            "u1@t.com", "Usuario Uno", PASSWORD, area=self.area, sucursal=self.sucursal
        )
        self.u2 = Usuario.objects.create_user(
            "u2@t.com", "Usuario Dos", PASSWORD, area=self.area, sucursal=self.sucursal
        )

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def post(self, *args, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(*args, **kwargs)

    def crear_ticket(self, autor=None, **extra):
        datos = {
            "titulo": "Falla de red",
            "descripcion": "No hay internet",
            "area": self.area,
            "creado_por": autor or self.u1,
        }
        datos.update(extra)
        return Ticket.objects.create(**datos)

    def gestionar(self, ticket, **campos):
        datos = {
            "guardar_gestion": "1",
            "estado": ticket.estado,
            "categoria": "",
            "numero_serie": "",
            "nota_resolucion": "",
        }
        datos.update(campos)
        return self.post(reverse("detalle_ticket", args=[ticket.pk]), datos)

    def resolver(self, ticket, nota="Se cambió el cable"):
        self.entrar(self.admin)
        self.gestionar(ticket, estado="POR_CONFIRMAR", nota_resolucion=nota)
        return self.url_del_correo()

    def url_del_correo(self):
        for correo in mail.outbox:
            encontrada = re.search(r"https?://[^\s]+/tickets/confirmar/[^\s]+/", correo.body)
            if encontrada:
                return encontrada.group(0).replace("http://localhost:8000", "")
        self.fail("No se envió el correo con el enlace de confirmación.")

    def destinatarios(self):
        return sorted(c.to[0] for c in mail.outbox)


class CreacionTicketTests(BaseTicketsTest):

    def test_el_formulario_solo_pide_titulo_descripcion_e_imagenes(self):
        self.entrar(self.u1)
        r = self.client.get(reverse("nuevo_ticket"))
        self.assertEqual(list(r.context["form"].fields), ["titulo", "descripcion", "imagenes"])
        self.assertContains(r, 'enctype="multipart/form-data"')
        self.assertContains(r, "multiple")

    def test_titulo_y_descripcion_son_obligatorios(self):
        self.entrar(self.u1)
        r = self.client.post(reverse("nuevo_ticket"), {"titulo": "", "descripcion": ""})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.context["form"].errors), {"titulo", "descripcion"})
        self.assertEqual(Ticket.objects.count(), 0)

    def test_usuario_crea_ticket_con_area_historial_notificacion_y_correos(self):
        self.entrar(self.u1)
        r = self.post(reverse("nuevo_ticket"), {
            "titulo": "No imprime", "descripcion": "La impresora no responde",
        })
        ticket = Ticket.objects.get()
        self.assertRedirects(r, reverse("detalle_ticket", args=[ticket.pk]))

        self.assertEqual(ticket.estado, Ticket.Estado.ABIERTO)
        self.assertEqual(ticket.creado_por, self.u1)
        self.assertEqual(ticket.area, self.area)
        self.assertEqual(ticket.historial.get().tipo, Historial.Tipo.CREACION)

        self.assertEqual(
            set(Notificacion.objects.values_list("usuario_id", flat=True)),
            {self.admin.pk, self.admin2.pk},
        )

        self.assertEqual(self.destinatarios(), ["admin2@t.com", "admin@t.com", "u1@t.com"])
        para_admin = next(c for c in mail.outbox if c.to == ["admin@t.com"])
        self.assertIn("Nuevo ticket", para_admin.subject)
        self.assertIn("La impresora no responde", para_admin.body)
        self.assertIn("/tickets/acceso/", para_admin.body)
        para_usuario = next(c for c in mail.outbox if c.to == ["u1@t.com"])
        self.assertIn("Recibimos tu ticket", para_usuario.subject)

    def test_los_correos_no_salen_si_la_creacion_se_deshace(self):
        self.entrar(self.u1)
        with self.captureOnCommitCallbacks(execute=False) as pendientes:
            self.client.post(reverse("nuevo_ticket"), {"titulo": "A", "descripcion": "B"})
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(pendientes)

    def test_usuario_sin_area_puede_crear_ticket(self):
        sin_area = Usuario.objects.create_user(
            "sa@t.com", "Sin Area", PASSWORD, sucursal=self.sucursal
        )
        self.entrar(sin_area)
        self.post(reverse("nuevo_ticket"), {"titulo": "Algo", "descripcion": "Pasa algo"})
        self.assertIsNone(Ticket.objects.get().area)

    def test_un_fallo_del_correo_no_rompe_la_creacion(self):
        self.entrar(self.u1)
        with mock.patch("django.core.mail.get_connection", side_effect=OSError("sin red")):
            with self.assertLogs("apps.tickets.emails", level="ERROR"):
                r = self.post(reverse("nuevo_ticket"), {"titulo": "A", "descripcion": "B"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_no_se_manda_correo_a_usuarios_inactivos_ni_sin_correo(self):
        Usuario.objects.filter(pk=self.admin2.pk).update(activo=False)
        self.entrar(self.u1)
        self.post(reverse("nuevo_ticket"), {"titulo": "A", "descripcion": "B"})
        self.assertEqual(self.destinatarios(), ["admin@t.com", "u1@t.com"])

    def test_el_asunto_con_saltos_de_linea_no_rompe_el_correo(self):
        self.entrar(self.u1)
        self.post(reverse("nuevo_ticket"), {"titulo": "Línea1\nLínea2", "descripcion": "x"})
        self.assertEqual(len(mail.outbox), 3)
        self.assertTrue(all("\n" not in c.subject for c in mail.outbox))


class AdjuntosTests(BaseTicketsTest):

    def crear_con_imagen(self, **extra):
        self.entrar(self.u1)
        datos = {"titulo": "Pantalla rota", "descripcion": "Mira la foto", "imagenes": imagen()}
        datos.update(extra)
        return self.post(reverse("nuevo_ticket"), datos)

    def test_adjunta_una_imagen_y_se_guarda_en_la_base(self):
        self.crear_con_imagen()
        adjunto = AdjuntoTicket.objects.get()
        self.assertEqual(adjunto.ticket, Ticket.objects.get())
        self.assertEqual(adjunto.subido_por, self.u1)
        self.assertEqual(adjunto.tipo_contenido, "image/jpeg")
        self.assertTrue(bytes(adjunto.contenido).startswith(b"\xff\xd8"))
        self.assertEqual(adjunto.tamano, len(bytes(adjunto.contenido)))

    def test_adjunta_varias_imagenes(self):
        self.entrar(self.u1)
        self.post(reverse("nuevo_ticket"), {
            "titulo": "Varias", "descripcion": "x",
            "imagenes": [imagen("a.jpg"), imagen("b.png", formato="PNG")],
        })
        self.assertEqual(AdjuntoTicket.objects.count(), 2)

    def test_el_adjunto_es_opcional(self):
        self.entrar(self.u1)
        self.post(reverse("nuevo_ticket"), {"titulo": "Sin foto", "descripcion": "x"})
        self.assertEqual(AdjuntoTicket.objects.count(), 0)
        self.assertEqual(Ticket.objects.count(), 1)

    def test_las_fotos_grandes_se_reducen(self):
        self.crear_con_imagen(imagenes=imagen("grande.jpg", tamano=(4000, 3000)))
        adjunto = AdjuntoTicket.objects.get()
        ancho, alto = Image.open(BytesIO(bytes(adjunto.contenido))).size
        self.assertEqual(max(ancho, alto), 1600)

    def test_un_archivo_que_no_es_imagen_se_rechaza_y_no_crea_ticket(self):
        falso = SimpleUploadedFile("virus.jpg", b"esto no es una imagen", content_type="image/jpeg")
        r = self.crear_con_imagen(imagenes=falso)
        self.assertEqual(r.status_code, 200)
        self.assertIn("imagenes", r.context["form"].errors)
        self.assertEqual(Ticket.objects.count(), 0)

    @override_settings(ADJUNTOS_MAX_ARCHIVOS=2)
    def test_limite_de_cantidad_de_imagenes(self):
        r = self.crear_con_imagen(imagenes=[imagen(f"{i}.jpg") for i in range(3)])
        self.assertIn("imagenes", r.context["form"].errors)
        self.assertEqual(Ticket.objects.count(), 0)

    @override_settings(ADJUNTOS_MAX_MB=0)
    def test_limite_de_peso_por_imagen(self):
        r = self.crear_con_imagen()
        self.assertIn("imagenes", r.context["form"].errors)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_solo_se_permiten_jpg_y_png(self):
        r = self.crear_con_imagen(imagenes=imagen("foto.gif", formato="GIF"))
        self.assertIn("imagenes", r.context["form"].errors)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_png_o_jpg_validos_se_aceptan(self):
        self.crear_con_imagen(imagenes=imagen("captura.png", formato="PNG"))
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(AdjuntoTicket.objects.count(), 1)

    def test_se_muestran_en_el_detalle_del_ticket(self):
        self.crear_con_imagen()
        ticket = Ticket.objects.get()
        adjunto = AdjuntoTicket.objects.get()
        r = self.client.get(reverse("detalle_ticket", args=[ticket.pk]))
        self.assertContains(r, reverse("ver_adjunto", args=[adjunto.pk]))

    def test_el_dueno_y_el_admin_ven_la_imagen_pero_otro_usuario_no(self):
        self.crear_con_imagen()
        url = reverse("ver_adjunto", args=[AdjuntoTicket.objects.get().pk])

        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/jpeg")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")

        self.entrar(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.entrar(self.u2)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)


class PermisosTicketsTests(BaseTicketsTest):

    def test_usuario_no_ve_tickets_ajenos(self):
        ticket = self.crear_ticket(autor=self.u1)
        self.entrar(self.u2)
        self.assertEqual(
            self.client.get(reverse("detalle_ticket", args=[ticket.pk])).status_code, 404
        )

    def test_lista_de_usuario_solo_muestra_sus_tickets(self):
        propio = self.crear_ticket(autor=self.u1, titulo="Mio")
        ajeno = self.crear_ticket(autor=self.u2, titulo="Ajeno")
        self.entrar(self.u1)
        r = self.client.get(reverse("lista_tickets"))
        self.assertContains(r, propio.titulo)
        self.assertNotContains(r, ajeno.titulo)

    def test_usuario_no_puede_gestionar_ticket(self):
        ticket = self.crear_ticket(autor=self.u1)
        self.entrar(self.u1)
        r = self.gestionar(ticket, estado="EN_PROCESO")
        self.assertEqual(r.status_code, 403)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.ABIERTO)

    def test_admin_ve_todos_los_tickets(self):
        t1 = self.crear_ticket(autor=self.u1, titulo="Ticket Usuario Uno")
        t2 = self.crear_ticket(autor=self.u2, titulo="Ticket Usuario Dos")
        self.entrar(self.admin)
        r = self.client.get(reverse("lista_tickets"))
        self.assertContains(r, t1.titulo)
        self.assertContains(r, t2.titulo)


class GestionTicketsTests(BaseTicketsTest):

    def test_el_admin_no_puede_cerrar_directamente(self):
        ticket = self.crear_ticket()
        self.entrar(self.admin)
        r = self.gestionar(ticket, estado="CERRADO", nota_resolucion="listo")
        self.assertEqual(r.status_code, 200)
        self.assertIn("estado", r.context["form_gestion"].errors)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.ABIERTO)
        self.assertEqual(len(mail.outbox), 0)

    def test_el_selector_de_estado_no_ofrece_cerrado(self):
        ticket = self.crear_ticket()
        self.entrar(self.admin)
        r = self.client.get(reverse("detalle_ticket", args=[ticket.pk]))
        valores = [v for v, _ in r.context["form_gestion"].fields["estado"].choices]
        self.assertEqual(valores, ["ABIERTO", "EN_PROCESO", "EN_ESPERA", "POR_CONFIRMAR"])

    def test_por_confirmar_exige_nota_de_resolucion(self):
        ticket = self.crear_ticket()
        self.entrar(self.admin)
        r = self.gestionar(ticket, estado="POR_CONFIRMAR", nota_resolucion="   ")
        self.assertEqual(r.status_code, 200)
        self.assertIn("nota_resolucion", r.context["form_gestion"].errors)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.ABIERTO)

    def test_en_proceso_avisa_al_usuario_por_correo_y_en_la_app(self):
        ticket = self.crear_ticket(autor=self.u1)
        self.entrar(self.admin)
        r = self.gestionar(ticket, estado="EN_PROCESO")
        self.assertEqual(r.status_code, 302)

        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.EN_PROCESO)
        self.assertEqual(ticket.historial.get().tipo, Historial.Tipo.CAMBIO_ESTADO)

        self.assertEqual(self.destinatarios(), ["u1@t.com"])
        self.assertIn("En proceso", mail.outbox[0].subject)
        self.assertEqual(Notificacion.objects.get().usuario, self.u1)

    def test_por_confirmar_manda_correo_con_enlace_y_no_cierra(self):
        ticket = self.crear_ticket(autor=self.u1)
        url = self.resolver(ticket)

        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.POR_CONFIRMAR)
        self.assertIsNotNone(ticket.resuelto_en)
        self.assertIsNone(ticket.cerrado_en)
        self.assertEqual(ticket.nota_resolucion, "Se cambió el cable")

        self.assertEqual(self.destinatarios(), ["u1@t.com"])
        correo = mail.outbox[0]
        self.assertIn("Se cambió el cable", correo.body)
        self.assertIn("/tickets/confirmar/", correo.body)
        self.assertTrue(url.startswith("/tickets/confirmar/"))

        n = Notificacion.objects.get(usuario=self.u1)
        self.assertEqual(n.tipo, Notificacion.Tipo.POR_CONFIRMAR)

    def test_reabrir_limpia_resolucion_y_nota(self):
        ticket = self.crear_ticket(autor=self.u1)
        self.resolver(ticket)
        self.gestionar(ticket, estado="EN_PROCESO")
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.EN_PROCESO)
        self.assertIsNone(ticket.resuelto_en)
        self.assertIsNone(ticket.cerrado_en)
        self.assertEqual(ticket.nota_resolucion, "")

    def test_un_ticket_cerrado_se_puede_reabrir(self):
        ticket = self.crear_ticket(
            estado="CERRADO", nota_resolucion="ok", cerrado_en=timezone.now()
        )
        self.entrar(self.admin)
        r = self.client.get(reverse("detalle_ticket", args=[ticket.pk]))
        self.assertIn("CERRADO", [v for v, _ in r.context["form_gestion"].fields["estado"].choices])
        self.gestionar(ticket, estado="EN_PROCESO")
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.EN_PROCESO)
        self.assertIsNone(ticket.cerrado_en)

    def test_admin_completa_numero_de_serie_y_categoria(self):
        ticket = self.crear_ticket()
        self.entrar(self.admin)
        self.gestionar(ticket, numero_serie="SN123", categoria=self.categoria.pk)
        ticket.refresh_from_db()
        self.assertEqual(ticket.numero_serie, "SN123")
        self.assertEqual(ticket.categoria, self.categoria)
        self.assertEqual(ticket.historial.get().tipo, Historial.Tipo.CATEGORIA)

    def test_service_tag_y_numero_de_serie_son_un_solo_campo(self):
        ticket = self.crear_ticket()
        self.entrar(self.admin)
        r = self.client.get(reverse("detalle_ticket", args=[ticket.pk]))
        campos = r.context["form_gestion"].fields
        self.assertIn("numero_serie", campos)
        self.assertNotIn("service_tag", campos)
        self.assertFalse(hasattr(Ticket, "service_tag"))
        self.assertContains(r, "Número de serie / Service Tag")

    def test_guardar_sin_cambios_no_genera_historial_ni_correos(self):
        ticket = self.crear_ticket()
        self.entrar(self.admin)
        self.gestionar(ticket)
        self.assertEqual(ticket.historial.count(), 0)
        self.assertEqual(len(mail.outbox), 0)


class ConfirmacionPorCorreoTests(BaseTicketsTest):

    def preparar(self):
        ticket = self.crear_ticket(autor=self.u1)
        url = self.resolver(ticket)
        mail.outbox.clear()
        self.client.logout()
        return ticket, url

    def test_abrir_el_enlace_solo_muestra_la_pantalla_y_no_cierra(self):
        ticket, url = self.preparar()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Se cambió el cable")
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.POR_CONFIRMAR)

    def test_confirmar_cierra_el_ticket_y_avisa(self):
        ticket, url = self.preparar()
        r = self.post(url, {"accion": "confirmar"})
        self.assertContains(r, "Ticket cerrado")

        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.CERRADO)
        self.assertIsNotNone(ticket.cerrado_en)
        self.assertIn("confirmó", ticket.historial.last().contenido)
        self.assertEqual(ticket.historial.last().usuario, self.u1)

        self.assertEqual(self.destinatarios(), ["admin2@t.com", "admin@t.com", "u1@t.com"])
        self.assertEqual(
            set(Notificacion.objects.filter(tipo=Notificacion.Tipo.TICKET_CERRADO)
                .values_list("usuario_id", flat=True)),
            {self.admin.pk, self.admin2.pk},
        )

    def test_rechazar_reabre_el_ticket_con_el_motivo(self):
        ticket, url = self.preparar()
        r = self.post(url, {"accion": "rechazar", "motivo": "Sigue sin internet"})
        self.assertContains(r, "Ticket reabierto")

        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.EN_PROCESO)
        self.assertIsNone(ticket.resuelto_en)
        self.assertIsNone(ticket.cerrado_en)
        self.assertIn("Sigue sin internet", ticket.historial.last().contenido)

        self.assertEqual(self.destinatarios(), ["admin2@t.com", "admin@t.com"])
        self.assertIn("Sigue sin internet", mail.outbox[0].body)
        self.assertTrue(Notificacion.objects.filter(tipo=Notificacion.Tipo.CIERRE_RECHAZADO).exists())

    def test_el_enlace_no_sirve_dos_veces(self):
        ticket, url = self.preparar()
        self.post(url, {"accion": "confirmar"})
        mail.outbox.clear()
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.post(url, {"accion": "confirmar"}).status_code, 400)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(ticket.historial.filter(tipo=Historial.Tipo.CAMBIO_ESTADO).count(), 2)

    def test_enlace_alterado_o_inventado_se_rechaza(self):
        ticket, url = self.preparar()
        self.assertEqual(self.client.get(url[:-3] + "xx/").status_code, 400)
        self.assertEqual(self.client.get("/tickets/confirmar/inventado/").status_code, 400)

    @override_settings(CIERRE_TOKEN_MAX_AGE=-1)
    def test_enlace_caducado(self):
        ticket, url = self.preparar()
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.post(url, {"accion": "confirmar"}).status_code, 400)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.POR_CONFIRMAR)

    def test_enlace_viejo_no_sirve_si_el_ticket_se_reabrio_y_se_resolvio_otra_vez(self):
        ticket, url_vieja = self.preparar()
        self.entrar(self.admin)
        self.gestionar(ticket, estado="EN_PROCESO")
        self.gestionar(ticket, estado="POR_CONFIRMAR", nota_resolucion="Ahora sí")
        self.client.logout()
        self.assertEqual(self.client.get(url_vieja).status_code, 400)
        self.assertEqual(self.client.get(self.url_del_correo_ultimo()).status_code, 200)

    def url_del_correo_ultimo(self):
        for correo in reversed(mail.outbox):
            m = re.search(r"https?://[^\s]+/tickets/confirmar/[^\s]+/", correo.body)
            if m:
                return m.group(0).replace("http://localhost:8000", "")
        self.fail("sin enlace")

    def test_acciones_desconocidas_no_cambian_nada(self):
        ticket, url = self.preparar()
        r = self.post(url, {"accion": "borrar"})
        self.assertEqual(r.status_code, 200)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.POR_CONFIRMAR)


class ConfirmacionEnLaAppTests(BaseTicketsTest):

    def preparar(self):
        ticket = self.crear_ticket(autor=self.u1)
        self.resolver(ticket)
        mail.outbox.clear()
        return ticket

    def test_el_usuario_ve_los_botones_y_el_admin_ve_que_se_espera_respuesta(self):
        ticket = self.preparar()
        url = reverse("detalle_ticket", args=[ticket.pk])

        self.entrar(self.u1)
        self.assertContains(self.client.get(url), "Sí, quedó resuelto")

        self.entrar(self.admin)
        r = self.client.get(url)
        self.assertNotContains(r, "Sí, quedó resuelto")
        self.assertContains(r, "Esperando que")

    def test_el_usuario_confirma_desde_la_app(self):
        ticket = self.preparar()
        self.entrar(self.u1)
        r = self.post(reverse("responder_cierre", args=[ticket.pk]), {"accion": "confirmar"})
        self.assertRedirects(r, reverse("detalle_ticket", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.CERRADO)
        self.assertIsNotNone(ticket.cerrado_en)

    def test_el_usuario_rechaza_desde_la_app(self):
        ticket = self.preparar()
        self.entrar(self.u1)
        self.post(reverse("responder_cierre", args=[ticket.pk]), {"accion": "rechazar", "motivo": "Falla"})
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.EN_PROCESO)

    def test_solo_el_creador_puede_responder(self):
        ticket = self.preparar()
        for quien in (self.u2, self.admin):
            self.entrar(quien)
            r = self.post(reverse("responder_cierre", args=[ticket.pk]), {"accion": "confirmar"})
            self.assertEqual(r.status_code, 404)
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.POR_CONFIRMAR)

    def test_responder_solo_por_post(self):
        ticket = self.preparar()
        self.entrar(self.u1)
        self.assertEqual(self.client.get(reverse("responder_cierre", args=[ticket.pk])).status_code, 405)


class ForzarCierreTests(BaseTicketsTest):

    def test_admin_cierra_sin_confirmacion_y_queda_registrado(self):
        ticket = self.crear_ticket(autor=self.u1)
        self.resolver(ticket)
        mail.outbox.clear()

        r = self.post(
            reverse("forzar_cierre", args=[ticket.pk]),
            {"justificacion": "El usuario no respondió en una semana"},
        )
        self.assertRedirects(r, reverse("detalle_ticket", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.CERRADO)
        self.assertIsNotNone(ticket.cerrado_en)
        self.assertIn("sin confirmación", ticket.historial.last().contenido)
        self.assertEqual(self.destinatarios(), ["u1@t.com"])

    def test_solo_aplica_a_tickets_por_confirmar(self):
        ticket = self.crear_ticket()
        self.entrar(self.admin)
        self.post(reverse("forzar_cierre", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.ABIERTO)

    def test_un_usuario_normal_no_puede(self):
        ticket = self.crear_ticket(autor=self.u1, estado="POR_CONFIRMAR", resuelto_en=timezone.now())
        self.entrar(self.u1)
        self.post(reverse("forzar_cierre", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.estado, Ticket.Estado.POR_CONFIRMAR)


class EnvioDeCorreosTests(TestCase):

    def test_si_un_correo_falla_los_demas_se_siguen_enviando(self):
        primero = mail.EmailMessage("A", "x", "h@t.com", ["rechazado@t.com"])
        segundo = mail.EmailMessage("B", "x", "h@t.com", ["bien@t.com"])
        original = locmem.EmailBackend.send_messages

        def falla_el_primero(self, mensajes):
            if mensajes[0].to == ["rechazado@t.com"]:
                raise OSError("dirección rechazada")
            return original(self, mensajes)

        with mock.patch.object(locmem.EmailBackend, "send_messages", falla_el_primero):
            with self.assertLogs("apps.tickets.emails", level="ERROR"):
                emails._enviar([primero, segundo])
        self.assertEqual([c.to for c in mail.outbox], [["bien@t.com"]])


class ProbarCorreoTests(TestCase):

    def test_manda_un_correo_de_prueba_al_destino_indicado(self):
        salida = StringIO()
        call_command("probar_correo", "destino@t.com", stdout=salida)
        self.assertEqual([c.to for c in mail.outbox], [["destino@t.com"]])
        self.assertIn("enviado", salida.getvalue())

    @override_settings(EMAIL_HOST_USER="")
    def test_sin_destino_ni_remitente_pide_el_destino(self):
        with self.assertRaises(CommandError):
            call_command("probar_correo", stdout=StringIO())

    def test_si_el_proveedor_falla_el_error_se_muestra(self):
        with mock.patch("django.core.mail.get_connection", side_effect=OSError("sin red")):
            with self.assertRaisesMessage(CommandError, "sin red"):
                call_command("probar_correo", "destino@t.com", stdout=StringIO())

class NotificacionesTests(BaseTicketsTest):

    def test_marcar_leida_y_abrir_notificacion(self):
        ticket = self.crear_ticket(autor=self.u1)
        n = Notificacion.objects.create(
            usuario=self.u1, ticket=ticket, tipo=Notificacion.Tipo.CAMBIO_ESTADO, mensaje="m"
        )
        self.entrar(self.u1)
        r = self.client.post(reverse("abrir_notificacion", args=[n.pk]))
        self.assertRedirects(r, reverse("detalle_ticket", args=[ticket.pk]))
        n.refresh_from_db()
        self.assertTrue(n.leida)
        self.assertIsNotNone(n.leida_en)

    def test_no_se_puede_tocar_notificacion_de_otro(self):
        n = Notificacion.objects.create(
            usuario=self.u1, tipo=Notificacion.Tipo.CAMBIO_ESTADO, mensaje="m"
        )
        self.entrar(self.u2)
        self.assertEqual(
            self.client.post(reverse("marcar_notificacion_leida", args=[n.pk])).status_code, 404
        )

    def test_leer_todas_y_contador_en_el_menu(self):
        for _ in range(3):
            Notificacion.objects.create(
                usuario=self.u1, tipo=Notificacion.Tipo.CAMBIO_ESTADO, mensaje="m"
            )
        self.entrar(self.u1)
        r = self.client.get(reverse("lista_notificaciones"))
        self.assertEqual(r.context["notificaciones_sin_leer"], 3)
        self.client.post(reverse("notificaciones_leer_todas"))
        r = self.client.get(reverse("lista_notificaciones"))
        self.assertEqual(r.context["notificaciones_sin_leer"], 0)


class FiltrosTests(BaseTicketsTest):

    def test_busqueda_y_filtros_del_panel(self):
        self.crear_ticket(autor=self.u1, titulo="Impresora rota", categoria=self.categoria)
        otro = self.crear_ticket(autor=self.u2, titulo="Excel se cierra", estado="CERRADO")
        self.entrar(self.admin)
        url = reverse("lista_tickets")

        def cuantos(**params):
            return self.client.get(url, params).context["page_obj"].paginator.count

        self.assertEqual(cuantos(q="impresora"), 1)
        self.assertEqual(cuantos(q=otro.titulo), 1)
        self.assertEqual(cuantos(q="Usuario Dos"), 1)
        self.assertEqual(cuantos(estado="CERRADO"), 1)
        self.assertEqual(cuantos(categoria=self.categoria.pk), 1)
        self.assertEqual(cuantos(area=self.area.pk), 2)

    def test_filtra_por_estado_por_confirmar(self):
        self.crear_ticket(estado="POR_CONFIRMAR", resuelto_en=timezone.now())
        self.crear_ticket()
        self.entrar(self.admin)
        r = self.client.get(reverse("lista_tickets"), {"estado": "POR_CONFIRMAR"})
        self.assertEqual(r.context["page_obj"].paginator.count, 1)
        self.assertEqual(r.context["conteos"]["por_confirmar"], 1)

    def test_parametros_invalidos_no_rompen_la_pagina(self):
        self.entrar(self.admin)
        r = self.client.get(
            reverse("lista_tickets"),
            {"estado": "XX", "area": "abc", "categoria": "1;drop", "page": "zzz"},
        )
        self.assertEqual(r.status_code, 200)

    def test_conteos_ignoran_los_filtros_y_activos_no_incluye_cerrados(self):
        self.crear_ticket()
        self.crear_ticket(estado="POR_CONFIRMAR", resuelto_en=timezone.now())
        self.crear_ticket(estado="CERRADO")
        self.entrar(self.admin)
        r = self.client.get(reverse("lista_tickets"), {"estado": "CERRADO"})
        self.assertEqual(r.context["conteos"]["total"], 3)
        self.assertEqual(r.context["conteos"]["activos"], 2)

    def test_pantallas_de_lista_y_reportes_cargan_con_todos_los_estados(self):
        self.crear_ticket(autor=self.u1)
        self.crear_ticket(autor=self.u1, estado="POR_CONFIRMAR", resuelto_en=timezone.now())
        self.entrar(self.u1)
        self.assertContains(self.client.get(reverse("lista_tickets")), "Por confirmar")
        self.entrar(self.admin)
        self.assertContains(self.client.get(reverse("lista_tickets")), "Por confirmar")
        r = self.client.get(reverse("reportes"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["graficas"]["distribucion"]["data"], [1, 0, 1, 0, 0])

class ConversacionYEsperaTests(BaseTicketsTest):

    def setUp(self):
        super().setUp()
        self.encargado = Usuario.objects.create_user(
            "enc@t.com", "Encargado", PASSWORD, rol="ENCARGADO", sucursal=self.sucursal
        )
        self.becario = Usuario.objects.create_user(
            "bec@t.com", "Becario", PASSWORD, rol="BECARIO", sucursal=self.sucursal
        )
        self.ticket = self.crear_ticket(autor=self.u1, sucursal=self.sucursal)
        mail.outbox.clear()

    def comentar(self, quien, contenido="Hola", **extra):
        self.entrar(quien)
        return self.post(
            reverse("comentar_ticket", args=[self.ticket.pk]),
            {"contenido": contenido, **extra},
        )

    def test_el_usuario_escribe_y_se_avisa_al_personal_de_la_sucursal(self):
        self.comentar(self.u1, "Ya probé reiniciar")
        self.assertEqual(self.ticket.comentarios.get().contenido, "Ya probé reiniciar")
        self.assertEqual(
            set(Notificacion.objects.values_list("usuario_id", flat=True)),
            {self.admin.pk, self.admin2.pk, self.encargado.pk, self.becario.pk},
        )
        self.assertEqual(
            self.destinatarios(),
            ["admin2@t.com", "admin@t.com", "bec@t.com", "enc@t.com"],
        )

    def test_el_tecnico_responde_y_se_avisa_al_solicitante(self):
        self.comentar(self.becario, "¿Qué modelo es el equipo?")
        self.assertEqual(
            list(Notificacion.objects.values_list("usuario_id", flat=True)),
            [self.u1.pk],
        )
        self.assertEqual(self.destinatarios(), ["u1@t.com"])

    def test_la_nota_interna_no_la_ve_el_usuario_ni_le_llega_aviso(self):
        self.comentar(self.becario, "Nota solo para el equipo", interno="on")
        self.assertTrue(self.ticket.comentarios.get().interno)
        self.assertEqual(mail.outbox, [])
        self.assertFalse(Notificacion.objects.filter(usuario=self.u1).exists())
        self.entrar(self.u1)
        self.assertNotContains(
            self.client.get(reverse("detalle_ticket", args=[self.ticket.pk])),
            "Nota solo para el equipo",
        )
        self.entrar(self.encargado)
        self.assertContains(
            self.client.get(reverse("detalle_ticket", args=[self.ticket.pk])),
            "Nota solo para el equipo",
        )

    def test_un_usuario_no_puede_marcar_su_mensaje_como_interno(self):
        self.comentar(self.u1, "Mensaje", interno="on")
        self.assertFalse(self.ticket.comentarios.get().interno)

    def test_no_se_comenta_en_ticket_cerrado_ni_en_ticket_ajeno(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(estado="CERRADO")
        self.comentar(self.u1, "Tarde")
        self.assertEqual(self.ticket.comentarios.count(), 0)
        Ticket.objects.filter(pk=self.ticket.pk).update(estado="ABIERTO")
        r = self.comentar(self.u2, "Intruso")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.ticket.comentarios.count(), 0)

    def test_poner_en_espera_exige_motivo(self):
        self.entrar(self.becario)
        r = self.gestionar(self.ticket, estado="EN_ESPERA", motivo_espera="  ")
        self.assertEqual(r.status_code, 200)
        self.assertIn("motivo_espera", r.context["form_gestion"].errors)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.ABIERTO)

    def test_becario_pone_en_espera_y_se_avisa_al_encargado(self):
        self.entrar(self.becario)
        self.gestionar(self.ticket, estado="EN_ESPERA", motivo_espera="Falta un cable HDMI")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.EN_ESPERA)
        self.assertIn("Falta un cable HDMI", self.ticket.historial.last().contenido)
        avisos = Notificacion.objects.filter(tipo=Notificacion.Tipo.ESPERA_MATERIALES)
        self.assertEqual(list(avisos.values_list("usuario_id", flat=True)), [self.encargado.pk])
        self.assertEqual(self.destinatarios(), ["enc@t.com", "u1@t.com"])

    def test_encargado_pone_en_espera_y_solo_queda_en_el_historial(self):
        self.entrar(self.encargado)
        self.gestionar(self.ticket, estado="EN_ESPERA", motivo_espera="Esperando la compra")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.EN_ESPERA)
        self.assertIn("Esperando la compra", self.ticket.historial.last().contenido)
        self.assertFalse(
            Notificacion.objects.filter(tipo=Notificacion.Tipo.ESPERA_MATERIALES).exists()
        )
        self.assertEqual(self.destinatarios(), ["u1@t.com"])

    def test_se_puede_retomar_un_ticket_en_espera(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(estado="EN_ESPERA")
        self.entrar(self.becario)
        self.gestionar(self.ticket, estado="EN_PROCESO")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.estado, Ticket.Estado.EN_PROCESO)

