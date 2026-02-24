from __future__ import annotations

from contextvars import ContextVar, Token


_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")


def set_correlation_id(value: str) -> Token[str]:
    return _correlation_id_ctx.set(value)


def get_correlation_id() -> str:
    return _correlation_id_ctx.get()


def reset_correlation_id(token: Token[str]) -> None:
    _correlation_id_ctx.reset(token)
