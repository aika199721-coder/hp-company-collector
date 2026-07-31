"""Pipeline-specific exception types."""


class PipelinePayloadError(ValueError):
    """Raised when a persisted task cannot restore its processing context."""
