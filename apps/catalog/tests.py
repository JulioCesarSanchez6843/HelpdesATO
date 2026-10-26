from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Usuario
from apps.tickets.models import Ticket
from .models import Area, Categoria, Puesto, Sucursal

PASSWORD = "pw-segura-123"


class CatalogosTests(TestCase):
    def setUp(self):
        self.sucursal = Sucursal.objects.create(nombre="Central")
        self.admin = Usuario.objects.create_user("a@t.com", "Admin", PASSWORD, rol="SUPERADMIN")
        self.user = Usuario.objects.create_user("u@t.com", "User", PASSWORD, sucursal=self.sucursal)

    def test_usuario_normal_no_puede_crear_ni_ver(self):
        self.client.force_login(self.user)
        self.client.post(reverse("lista_areas"), {"nombre": "HACK"})
        self.assertFalse(Area.objects.filter(nombre="HACK").exists())
        self.assertRedirects(self.client.get(reverse("lista_areas")), reverse("lista_tickets"))

    def test_crud_de_los_tres_catalogos(self):
        self.client.force_login(self.admin)
        for clave, modelo in (("areas", Area), ("categorias", Categoria), ("puestos", Puesto)):
            self.client.post(reverse(f"lista_{clave}"), {"nombre": "  Uno   Dos "})
            registro = modelo.objects.get()
            self.assertEqual(registro.nombre, "Uno Dos")
            self.client.post(reverse(f"editar_{clave}", args=[registro.pk]), {"nombre": "Nuevo"})
            registro.refresh_from_db()
            self.assertEqual(registro.nombre, "Nuevo")
            self.client.post(reverse(f"eliminar_{clave}", args=[registro.pk]))
            self.assertFalse(modelo.objects.exists())

    def test_nombre_duplicado_no_da_error_500(self):
        Area.objects.create(nombre="Contabilidad")
        self.client.force_login(self.admin)
        r = self.client.post(reverse("lista_areas"), {"nombre": "contabilidad"}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Area.objects.count(), 1)
        self.assertContains(r, "Ya existe")

    def test_no_se_elimina_lo_que_esta_en_uso(self):
        area = Area.objects.create(nombre="Ventas")
        cat = Categoria.objects.create(nombre="Red")
        puesto = Puesto.objects.create(nombre="Jefe")
        Ticket.objects.create(titulo="t", descripcion="d", area=area, categoria=cat, creado_por=self.user)
        Usuario.objects.filter(pk=self.user.pk).update(puesto=puesto)
        self.client.force_login(self.admin)
        self.client.post(reverse("eliminar_areas", args=[area.pk]))
        self.client.post(reverse("eliminar_categorias", args=[cat.pk]))
        self.client.post(reverse("eliminar_puestos", args=[puesto.pk]))
        self.assertTrue(Area.objects.exists() and Categoria.objects.exists() and Puesto.objects.exists())

    def test_eliminar_solo_por_post(self):
        area = Area.objects.create(nombre="Ventas")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("eliminar_areas", args=[area.pk])).status_code, 405)

    def test_las_pantallas_de_lista_cargan(self):
        Area.objects.create(nombre="Ventas")
        self.client.force_login(self.admin)
        for clave in ("areas", "categorias", "puestos"):
            self.assertEqual(self.client.get(reverse(f"lista_{clave}")).status_code, 200)

class DesactivarSucursalTests(TestCase):
    def setUp(self):
        self.sucursal = Sucursal.objects.create(nombre="Norte")
        self.otra = Sucursal.objects.create(nombre="Sur")
        self.maestro = Usuario.objects.create_superuser("m@t.com", "Maestro", PASSWORD)
        self.super_en_norte = Usuario.objects.create_user(
            "s@t.com", "Super Norte", PASSWORD, rol="SUPERADMIN", sucursal=self.sucursal
        )
        self.activo = Usuario.objects.create_user(
            "a@t.com", "Activo", PASSWORD, sucursal=self.sucursal
        )
        self.de_sur = Usuario.objects.create_user(
            "d@t.com", "De Sur", PASSWORD, sucursal=self.otra
        )
        self.client.force_login(self.maestro)

    def test_desactiva_usuarios_y_conserva_tickets(self):
        ticket = Ticket.objects.create(
            titulo="t", descripcion="d", creado_por=self.activo, sucursal=self.sucursal
        )
        self.client.post(reverse("cambiar_estado_sucursal", args=[self.sucursal.pk]))
        for objeto in (self.sucursal, self.activo, self.super_en_norte, self.de_sur, ticket):
            objeto.refresh_from_db()
        self.assertFalse(self.sucursal.activa)
        self.assertFalse(self.activo.activo)
        self.assertEqual(self.activo.sucursal_id, self.sucursal.pk)
        self.assertTrue(self.super_en_norte.activo)
        self.assertTrue(self.de_sur.activo)
        self.assertEqual(ticket.estado, Ticket.Estado.ABIERTO)
        self.assertIsNone(ticket.cerrado_en)

    def test_activar_no_reactiva_usuarios(self):
        self.client.post(reverse("cambiar_estado_sucursal", args=[self.sucursal.pk]))
        self.client.post(reverse("cambiar_estado_sucursal", args=[self.sucursal.pk]))
        self.sucursal.refresh_from_db()
        self.activo.refresh_from_db()
        self.assertTrue(self.sucursal.activa)
        self.assertFalse(self.activo.activo)

    def test_no_activa_usuario_de_sucursal_inactiva(self):
        self.client.post(reverse("cambiar_estado_sucursal", args=[self.sucursal.pk]))
        self.client.post(reverse("cambiar_estado_usuario", args=[self.activo.pk]))
        self.activo.refresh_from_db()
        self.assertFalse(self.activo.activo)