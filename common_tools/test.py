from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from int.db_context import DatabaseContext


class BaseTestCase(TestCase):
    databases = {"default", "organization_1"}

    def setUp(self):
        super().setUp()
        cache.clear()

    @classmethod
    def setUpClass(cls):
        cls._db_context = DatabaseContext.using("organization_1")
        cls._db_context.__enter__()
        super().setUpClass()
        cls._set_patcher = patch(
            "int.db_context.DatabaseContext.set",
            lambda *_args, **_kwargs: None,
        )
        cls._set_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._set_patcher.stop()
        super().tearDownClass()
        cls._db_context.__exit__(None, None, None)
