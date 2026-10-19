from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Usuario
from .models import Area, Categoria, Puesto

PASSWORD = "pw-segura-123"


class CatalogosTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user("a@t.com", "Admin", PASSWORD, rol="ADMIN")
        self.user = Usuario.objects.create_user("u@t.com", "User", PASSWORD)

    def test_usuario_normal_no_puede_crear_ni_ver(self):
        self.client.force_login(self.user)
        self.client.post(reverse("lista_areas"), {"nombre": "HACK"})
        self.assertFalse(Area.objects.filter(nombre="HACK").exists())
        self.assertEqual(self.client.get(reverse("lista_areas")).status_code, 403)

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
        puesto = Puesto.objects.create(nombre="Jefe")
        Usuario.objects.filter(pk=self.user.pk).update(area=area, puesto=puesto)
        self.client.force_login(self.admin)
        self.client.post(reverse("eliminar_areas", args=[area.pk]))
        self.client.post(reverse("eliminar_puestos", args=[puesto.pk]))
        self.assertTrue(Area.objects.exists() and Puesto.objects.exists())

    def test_eliminar_solo_por_post(self):
        area = Area.objects.create(nombre="Ventas")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("eliminar_areas", args=[area.pk])).status_code, 405)

    def test_las_pantallas_de_lista_cargan(self):
        Area.objects.create(nombre="Ventas")
        self.client.force_login(self.admin)
        for clave in ("areas", "categorias", "puestos"):
            self.assertEqual(self.client.get(reverse(f"lista_{clave}")).status_code, 200)