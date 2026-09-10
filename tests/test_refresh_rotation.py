from sqlalchemy import inspect
from models.models import User

def test_refresh_tokens_table_exists(db_session):
    test_engine = db_session.get_bind()

    inspector = inspect(test_engine)

    table_names = inspector.get_table_names()

    assert "refresh_tokens" in table_names

from models.models import User


def test_test_user_is_saved(db_session, test_user):
    saved_user = db_session.get(User, test_user.id)

    assert saved_user is not None
    assert saved_user.username == "rotation_test_user"