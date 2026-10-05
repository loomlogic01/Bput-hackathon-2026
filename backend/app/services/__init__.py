"""
Service layer.

Modules here hold request-time business logic that is shared by more than one
router, or is substantial enough not to belong in an endpoint module. They keep
the API modules thin and make the logic directly testable.
"""