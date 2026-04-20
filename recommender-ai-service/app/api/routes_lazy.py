"""Wrapper for lazy-loading routes to avoid Django app registry issues."""

def get_router():
    """Lazy-load router after Django is setup to avoid app registry errors."""
    from .routes import router
    return router
