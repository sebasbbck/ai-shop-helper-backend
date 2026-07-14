import uuid
from collections.abc import Callable
from typing import Any

import pytest

from ai_shop_helper_backend.core.security import hash_password
from ai_shop_helper_backend.models.orgs import Org
from ai_shop_helper_backend.models.users import User


@pytest.fixture
def make_user() -> Callable[..., User]:
    """Return a factory that builds unsaved User instances with sensible defaults."""

    def factory(**kwargs: Any) -> User:
        """Build an unsaved User instance with sensible defaults.

        This factory function creates a User instance with default values for all required fields. You
        can override any of the defaults by passing keyword arguments.

        Args:
            **kwargs: Arbitrary keyword arguments to override default field values.

        Returns:
            User: An unsaved User instance with the specified field values.
        """
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "name": "Test User",
            "hashed_password": hash_password("password123"),
            "is_active": True,
            "is_superuser": False,
        }
        defaults.update(kwargs)
        return User(**defaults)

    return factory


@pytest.fixture
def make_org() -> Callable[..., Org]:
    """Return a factory that builds unsaved Org instances with sensible defaults."""

    def factory(**kwargs: Any) -> Org:
        """Build an unsaved Org instance with sensible defaults.

        Args:
            **kwargs: Arbitrary keyword arguments to override default field values.

        Returns:
            Org: An unsaved Org instance with the specified field values.
        """
        defaults: dict[str, Any] = {
            "id": uuid.uuid4(),
            "name": "Test Org",
            "subscription_credits": 0,
            "purchased_credits": 0,
        }
        defaults.update(kwargs)
        return Org(**defaults)

    return factory
