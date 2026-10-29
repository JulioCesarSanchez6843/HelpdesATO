# Helpdesk Tollocan

Sistema web de tickets de soporte técnico. Los usuarios de una organización reportan incidencias (red, hardware, software, impresoras, etc.) y el equipo de administradores las atiende, con seguimiento de principio a fin y avisos por correo.

Hecho con **Django 5** y **PostgreSQL**.

---

## Contenido

1. Cómo funciona
2. Qué necesitas instalar
3. Correr el proyecto en local
4. Variables de entorno
5. Comandos útiles
6. Problemas comunes
7. Desplegar en Render

---

## 1. Cómo funciona

### Roles

| Rol | Qué puede hacer |
|---|---|
| **Usuario** | Crear tickets (título, descripción y fotos opcionales), ver sus propios tickets, confirmar o rechazar la solución y recibir notificaciones. |
| **Administrador** | Ver todos los tickets, clasificarlos (categoría y número de serie / Service Tag), cambiar su estado, gestionar usuarios, administrar los catálogos y consultar reportes. |

El inicio de sesión se hace con **correo y contraseña**. El correo es obligatorio y único para todos.

### Ciclo de vida de un ticket

```
Abierto  →  En proceso  →  Por confirmar  →  Cerrado
```

1. El usuario crea el ticket. Su **área** se toma automáticamente de su perfil.
2. Los administradores reciben aviso (correo y notificación dentro del sistema).
3. Un administrador lo pasa a **En proceso** y lo clasifica.
4. Cuando lo resuelve, lo marca **Por confirmar** y escribe una nota de resolución (obligatoria).
5. El usuario recibe un correo con un enlace (firmado, sin iniciar sesión, caduca a los 7 días) y pulsa **«Sí, quedó resuelto»** o **«No está resuelto»**. Si lo rechaza, el ticket regresa a **En proceso**.
6. Si el usuario nunca responde, el administrador puede usar **«Cerrar sin confirmación del usuario»**, y queda registrado en el historial.

El administrador **no puede cerrar un ticket directamente**: el cierre lo confirma el usuario.

### Módulos principales

- **Tickets**: creación, listado, detalle con historial de eventos, adjuntos de imagen y notificaciones internas.
- **Usuarios** (solo admin): alta, edición, activación y desactivación.
- **Catálogos** (solo admin): áreas, categorías y puestos.
- **Reportes** (solo admin): totales por estado, porcentaje de resueltos, tiempo promedio de resolución y gráficas de actividad de los últimos 7 días.

### Detalles a tener en cuenta

- **Imágenes**: hasta 5 por ticket, de máximo 5 MB cada una. Se validan, se corrige su rotación y se reducen a 1600 px. Se guardan **en la base de datos** y solo las ven el dueño del ticket y los administradores.
- **Contraseñas**: nadie cambia la suya. Un administrador cambia la de los usuarios normales. Para cambiar la de **otro administrador**, este debe autorizarlo desde un enlace que le llega por correo.
- **Correos**: el sistema elige el envío según las variables que definas: API de Brevo, SMTP (Gmail u otro) o, si no hay nada configurado, **la consola** (los correos se imprimen en la terminal y no se envían).

---

## 2. Qué necesitas instalar

Antes de clonar el proyecto, instala estas tres herramientas.

### Python 3.12 o superior

1. Descárgalo de https://www.python.org/downloads/
2. En Windows, durante la instalación marca la casilla **Add python.exe to PATH**.
3. Comprueba que quedó instalado:

```bash
python --version
```

### PostgreSQL 14 o superior

1. Descárgalo de https://www.postgresql.org/download/ y elige tu sistema operativo. En Windows usa el instalador oficial.
2. Durante la instalación te pedirá una **contraseña para el usuario postgres**. Anótala, la vas a necesitar en el archivo `.env`.
3. Deja el puerto por defecto, **5432**.
4. Puedes dejar marcado **pgAdmin 4**, un programa con interfaz gráfica para administrar la base de datos.
5. Comprueba que el servicio está corriendo. En Windows aparece como `postgresql-x64-NN` en la app Servicios.

### Git

1. Descárgalo de https://git-scm.com/downloads
2. Instálalo con las opciones por defecto.
3. Comprueba que quedó instalado:

```bash
git --version
```

---

## 3. Correr el proyecto en local

### Paso 1. Clonar el repositorio

```bash
git clone https://github.com/<tu-usuario>/<tu-repositorio>.git
cd <tu-repositorio>
```

Reemplaza `<tu-usuario>` y `<tu-repositorio>` por los datos reales. Si el proyecto lo descargaste como ZIP, descomprímelo y entra a la carpeta que contiene `manage.py`.

### Paso 2. Crear y activar el entorno virtual

Un entorno virtual mantiene las librerías del proyecto separadas del resto de tu computadora.

En Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Si PowerShell bloquea el script con un error de políticas de ejecución, corre esto una sola vez y vuelve a activar:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

En Linux o macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

Sabrás que está activo cuando veas `(venv)` al inicio de la línea de tu terminal.

### Paso 3. Instalar las dependencias

```bash
pip install -r requirements/dev.txt
```

### Paso 4. Crear la base de datos en PostgreSQL

Elige una de las dos formas.

**Con pgAdmin:** abre pgAdmin, escribe la contraseña de postgres, haz clic derecho en **Databases**, elige **Create > Database**, escribe `helpdesk_db` y guarda.

**Con la terminal:** abre **SQL Shell (psql)**, que se instala junto con PostgreSQL. Presiona Enter en cada pregunta hasta que pida la contraseña, escribe la de postgres y ejecuta:

```sql
CREATE DATABASE helpdesk_db;
```

Para salir de psql escribe `\q`.

### Paso 5. Configurar las variables de entorno

Crea un archivo llamado `.env` en la raíz del proyecto, junto a `manage.py`, con este contenido, y cambia los valores que lo piden:

```env
SECRET_KEY=cambia-esto-por-una-clave-larga-y-aleatoria
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SETTINGS_MODULE=config.settings.dev

DB_NAME=helpdesk_db
DB_USER=postgres
DB_PASSWORD=tu_password_de_postgres
DB_HOST=localhost
DB_PORT=5432

SITE_URL=http://localhost:8000
```

Si el repositorio incluye un archivo `.env.example`, puedes copiarlo con otro nombre y editarlo:

```powershell
copy .env.example .env
```

Con esto basta para empezar. Mientras no configures correo, los mensajes salen en la consola donde corre el servidor.

### Paso 6. Aplicar las migraciones

Esto crea todas las tablas en la base de datos:

```bash
python manage.py migrate
```

### Paso 7. Crear el administrador inicial

```bash
python manage.py createsuperuser
```

Te pedirá correo, nombre y contraseña. Usa un correo que realmente revises, porque recibe los avisos de administración.

### Paso 8. Iniciar el servidor

```bash
python manage.py runserver
```

Abre http://localhost:8000 en el navegador e inicia sesión con el administrador que creaste. Para detener el servidor presiona `Ctrl + C`.

### Paso 9. Primeros pasos recomendados

Entra como administrador y, antes de crear tickets, da de alta los **catálogos** (Áreas y Categorías, y opcionalmente Puestos). Después crea los **usuarios** desde la sección *Usuarios*, asignándoles su área.

### Cada vez que vuelvas a trabajar

No repitas la instalación. Solo abre la terminal en la carpeta del proyecto y corre:

```powershell
.\venv\Scripts\Activate.ps1
python manage.py runserver
```

Si después de un `git pull` llegaron cambios nuevos, corre también `pip install -r requirements/dev.txt` y `python manage.py migrate`.

---

## 4. Variables de entorno

| Variable | Para qué sirve |
|---|---|
| `SECRET_KEY` | Clave secreta de Django. Debe ser larga, aleatoria y privada. |
| `DEBUG` | `True` solo en desarrollo. |
| `ALLOWED_HOSTS` | Dominios desde los que se puede abrir el sitio, separados por comas. |
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` en local y `config.settings.prod` en producción. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Datos de conexión a PostgreSQL. |
| `DATABASE_URL` | Alternativa a las variables `DB_*`. Si existe, tiene prioridad (es lo que usa Render). |
| `SITE_URL` | Dirección base que se usa en los enlaces de los correos. |
| `CIERRE_TOKEN_DIAS` | Días de vigencia del enlace para confirmar el cierre. Por defecto 7. |
| `PASSWORD_APROBACION_DIAS` | Días de vigencia del enlace para autorizar el cambio de contraseña de un administrador. Por defecto 3. |

Para generar una `SECRET_KEY` segura:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Correos reales con Gmail (opcional)

Agrega al `.env`:

```env
EMAIL_HOST_USER=tu-cuenta@gmail.com
EMAIL_HOST_PASSWORD=tu-contraseña-de-aplicación
DEFAULT_FROM_EMAIL=Helpdesk Tollocan <tu-cuenta@gmail.com>
```

`EMAIL_HOST_PASSWORD` debe ser una **contraseña de aplicación** de Google (requiere verificación en 2 pasos), no tu contraseña normal.

### Correos con Brevo (opcional)

Agrega al `.env` la clave de API de tu cuenta de Brevo y un remitente verificado:

```env
BREVO_API_KEY=tu-clave-de-api
DEFAULT_FROM_EMAIL=Helpdesk <tu-correo-verificado@gmail.com>
```

Si defines `BREVO_API_KEY`, se usa Brevo. Si no, y defines usuario y contraseña de Gmail, se usa SMTP. Si no defines nada, los correos salen en la consola.

---

## 5. Comandos útiles

```bash
python manage.py test                              # Ejecutar las pruebas automáticas
python manage.py probar_correo tucorreo@gmail.com  # Probar el envío de correos
python manage.py makemigrations --check            # Verificar que no falten migraciones
python manage.py check                             # Revisar la configuración del proyecto
```

---

## 6. Problemas comunes

**`password authentication failed for user "postgres"`**
La contraseña de `DB_PASSWORD` en el `.env` no es la que pusiste al instalar PostgreSQL.

**`database "helpdesk_db" does not exist`**
Falta crear la base de datos. Repite el Paso 4.

**`connection refused` o no se puede conectar al servidor**
El servicio de PostgreSQL no está corriendo, o `DB_HOST` y `DB_PORT` no coinciden con tu instalación.

**`ModuleNotFoundError: No module named 'django'`**
El entorno virtual no está activo o no instalaste las dependencias. Repite los Pasos 2 y 3.

**PowerShell no deja activar el entorno virtual**
Corre el comando de `Set-ExecutionPolicy` que aparece en el Paso 2.

**`Error: That port is already in use`**
Hay otro servidor corriendo. Ciérralo o inicia este en otro puerto con `python manage.py runserver 8001`.

**Los correos no llegan**
Sin configuración de correo, los mensajes solo se imprimen en la terminal del servidor. Revisa la sección de variables de entorno.

---

## 7. Desplegar en Render

El proyecto incluye `render.yaml` y `build.sh` para desplegarlo en Render con una base PostgreSQL.

1. Sube el repositorio a GitHub.
2. En Render elige **New > Blueprint** y selecciona el repositorio.
3. Render lee `render.yaml` y te pide los valores de estas variables:
   - `DJANGO_SUPERUSER_CORREO`: tu correo real. Recibe los avisos de administración.
   - `DJANGO_SUPERUSER_PASSWORD`: una contraseña segura para el administrador inicial.
   - `BREVO_API_KEY`: la clave de API de Brevo. El plan gratuito de Render bloquea SMTP, por eso los correos salen por la API de Brevo.
   - `DEFAULT_FROM_EMAIL`: el remitente, por ejemplo `Helpdesk <tu-correo-verificado-en-brevo@gmail.com>`.
4. En cada despliegue, `build.sh` instala dependencias, junta los archivos estáticos, aplica las migraciones y crea el administrador inicial si no existe.
5. Si usas un dominio propio, agrega la variable `SITE_URL` con la dirección completa, por ejemplo `https://tu-dominio.com`.

---

Hecho por **Juls**.

Colaborador **Cris**