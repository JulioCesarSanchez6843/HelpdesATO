from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.catalog.models import Area
from apps.tickets.models import Ticket


class ReportesTests(TestCase):
    def setUp(self):
        self.area = Area.objects.create(nombre="Ventas")
        self.admin = Usuario.objects.create_user("a@t.com", "Admin", "pw-segura-123", rol="ADMIN")
        self.user = Usuario.objects.create_user("u@t.com", "User", "pw-segura-123")

    def test_usuario_normal_no_entra(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("reportes"))
        self.assertRedirects(r, reverse("lista_tickets"))

    def test_sin_tickets_no_falla(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("reportes"))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.context["tiempo_promedio_horas"])
        self.assertEqual(r.context["porcentaje_resueltos"], 0)
        self.assertEqual(r.context["graficas"]["actividad"]["data"], [0] * 7)

    def test_kpis_y_actividad_reales(self):
        ahora = timezone.now()
        t = Ticket.objects.create(titulo="a", descripcion="d", area=self.area, creado_por=self.user)
        Ticket.objects.create(titulo="b", descripcion="d", area=self.area, creado_por=self.user)
        cerrado = Ticket.objects.create(
            titulo="c", descripcion="d", area=self.area, creado_por=self.user,
            estado="CERRADO", cerrado_en=ahora + timedelta(hours=4))
        Ticket.objects.filter(pk=cerrado.pk).update(creado_en=ahora)
        self.client.force_login(self.admin)
        ctx = self.client.get(reverse("reportes")).context
        self.assertEqual((ctx["total"], ctx["abiertos"], ctx["cerrados"]), (3, 2, 1))
        self.assertEqual(ctx["porcentaje_resueltos"], 33)
        self.assertEqual(ctx["tiempo_promedio_horas"], 4.0)
        self.assertEqual(sum(ctx["graficas"]["actividad"]["data"]), 3)
        self.assertEqual(ctx["graficas"]["actividad"]["data"][-1], 3)