"""Jerarquía de excepciones del motor.

Regla general: un error de *usuario* (acción ilegal, configuración imposible) hereda de
:class:`MusEngineError` y es recuperable; :class:`InvariantViolationError` indica un
bug del propio motor y nunca debe capturarse para continuar.
"""

from __future__ import annotations


class MusEngineError(Exception):
    """Base de todos los errores del motor."""


class InvalidConfigError(MusEngineError):
    """La configuración de la partida es imposible o incoherente."""


class InvalidCardError(MusEngineError):
    """Una carta no existe en la baraja configurada o su código es inválido."""


class InvalidDeckError(MusEngineError):
    """Una baraja tiene cartas duplicadas, ajenas o una composición incorrecta."""


class IllegalActionError(MusEngineError):
    """La acción no es legal en el estado actual de la partida."""


class NotYourTurnError(IllegalActionError):
    """El jugador intenta actuar fuera de su turno."""


class InvalidStateError(IllegalActionError):
    """La acción no corresponde a la fase actual."""


class InvalidBetError(IllegalActionError):
    """Importe de envite inválido, aceptar sin envite, revocar un órdago, etc."""


class InvalidDiscardError(IllegalActionError):
    """Descarte con número de cartas inválido o con cartas que no son del jugador."""


class InvalidPlayerError(MusEngineError):
    """El identificador de jugador no existe en la partida."""


class GameNotStartedError(MusEngineError):
    """Se ha pedido algo que requiere una partida iniciada."""


class GameFinishedError(MusEngineError):
    """La partida ha terminado y no admite más acciones."""


class PrivateInformationError(MusEngineError):
    """Se ha solicitado información a la que el solicitante no tiene derecho."""


class InvariantViolationError(MusEngineError):
    """Un invariante interno no se cumple: es un bug del motor."""
