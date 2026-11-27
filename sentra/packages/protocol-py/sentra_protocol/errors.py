"""Explicit exception hierarchy for SENTRA wire protocol, crypto, and replay errors."""

from __future__ import annotations


class SentraProtocolError(Exception):
    """Base class for all SENTRA wire protocol and cryptographic errors."""


class MalformedFrameError(SentraProtocolError):
    """Raised when a wire frame violates binary structure or framing invariants."""


class TruncatedFrameError(MalformedFrameError):
    """Raised when a wire frame or inner container is shorter than declared."""


class OversizedFrameError(MalformedFrameError):
    """Raised when a wire frame exceeds the maximum permitted payload cap."""


class UnsupportedVersionError(MalformedFrameError):
    """Raised when a frame declares an unsupported protocol version."""


class UnknownMessageTypeError(MalformedFrameError):
    """Raised when a frame carries an unrecognized message type byte."""


class InvalidKeyError(SentraProtocolError):
    """Raised when a cryptographic key cannot be resolved or has invalid length."""


class AuthenticationError(SentraProtocolError):
    """Raised when AES-256-GCM tag verification or AAD authentication fails."""


class IntegrityError(SentraProtocolError):
    """Raised when decrypted payload structure or SHA-256 media digests fail checks."""


class ReplayError(SentraProtocolError):
    """Raised when a frame violates monotonic epoch or sequence counter rules."""
