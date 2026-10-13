import pytest
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Test databases need the cache table too (normally made by `createcachetable`)."""
    with django_db_blocker.unblock():
        call_command("createcachetable")
