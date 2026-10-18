# Publicar MUS.ST en Internet (Fase C2)

La web se publica con **Render** usando el fichero `render.yaml` de la raíz, que crea
dos cosas gratuitas:

- un **servicio web** que construye el `Dockerfile` y arranca `python -m mus_web`;
- una **base de datos PostgreSQL** donde se guardan cuentas y partidas.

No hay que tocar código ni escribir contraseñas: Render conecta la base de datos con la
web por sí mismo (`MUSST_DATABASE_URL`) y activa las cookies seguras (`MUSST_SECURE=1`).

## Pasos (unos 10 minutos)

1. Entra en <https://render.com> y pulsa **Get Started**. Regístrate con
   **GitHub** (la misma cuenta del repositorio `saraatrapero/musst`).
2. Cuando Render pida acceso a GitHub, dale permiso al repositorio **musst** (basta
   con ese).
3. En el panel de Render: **New +** → **Blueprint**.
4. Elige el repositorio **saraatrapero/musst**, rama `main`. Render lee
   `render.yaml` y muestra `musst` (web) y `musst-db` (base de datos).
5. Pulsa **Apply** (o **Deploy Blueprint**). La primera construcción tarda unos minutos.
6. Cuando el servicio `musst` esté en verde (**Live**), su dirección aparece arriba,
   del estilo `https://musst-xxxx.onrender.com`. Esa es la web pública: ábrela,
   regístrate y juega.

Cada vez que se fusione un PR en `main`, Render vuelve a publicar la web sola.

## Comprobar que funciona

- `https://<tu-dirección>/healthz` debe responder `{"status":"ok"}` (servidor y base
  de datos bien).
- Regístrate, crea una sala «Tú + bot» y juega una mano.
- Para probar con amigos: crea una sala de «2 personas» o «4 personas» y pásales el
  código.

## Límites del plan gratuito

Son condiciones de Render que pueden cambiar; consúltalas en su web.

- El servicio **se duerme** tras un rato sin visitas; la primera visita después tarda
  alrededor de un minuto en despertarlo. Una partida a medias se pierde si se duerme
  o se vuelve a publicar (las terminadas quedan guardadas).
- La base de datos gratuita **caduca** pasado un tiempo (hasta ahora, 30 días): antes
  de que caduque hay que pasarla a un plan de pago o crear otra. Para la entrega y la
  defensa de la práctica conviene revisar la fecha en el panel de Render.

## Otros alojamientos

Cualquier servicio que ejecute Docker y ofrezca PostgreSQL vale (Railway, Fly.io…):
construir el `Dockerfile`, definir `MUSST_DATABASE_URL` con la dirección de la base
de datos (se acepta `postgres://…`) y `MUSST_SECURE=1`. Debe haber **un solo proceso**
servidor, porque las salas activas viven en memoria.
