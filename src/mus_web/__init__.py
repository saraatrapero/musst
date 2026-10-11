"""MUS.ST web: cuentas, salas y partidas en el navegador.

El servidor es la única autoridad: ejecuta el motor, valida cada acción y envía a cada
jugador **sólo su observación**. El navegador nunca recibe cartas ajenas.

Arranque en local::

    pip install -e ".[web]"
    python -m mus_web          # http://127.0.0.1:8000
"""
