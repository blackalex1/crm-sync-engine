import pytest
import sqlite3
from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Engine

from crm import Customer, Lead
from models import db, AbstractCustomer, AmoCustomer, AmoLead, AmoCompany, AmoContact


@event.listens_for(Engine, "connect")
def set_sqlite_lower(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("lower", 1, lambda s: s.lower() if s else s)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def session(app):
    return db.session


def make_customer(
    id: int,
    name: str = 'Test Customer',
    login: str = None,
    status_id: int = 0,
    companies=None,
    contacts=None,
    custom_fields=None
) -> Customer:
    cf = dict(custom_fields or {})
    if login is not None:
        cf['Логин'] = {'value': login}
    return Customer(
        id=id,
        name=name,
        next_price=0,
        next_date=0,
        responsible_user_id=1,
        status_id=status_id,
        periodicity=0,
        created_by=1,
        updated_by=1,
        created_at=0,
        updated_at=0,
        closest_task_at=0,
        is_deleted=False,
        ltv=0,
        purchases_count=0,
        average_check=0,
        account_id=1,
        custom_fields_values=cf,
        _embedded={
            'companies': companies or [],
            'contacts': contacts or []
        }
    )


def make_lead(
    id: int,
    name: str = 'Test Lead',
    login: str = None,
    status_id: int = 0,
    contacts=None,
    custom_fields=None
) -> Lead:
    cf = dict(custom_fields or {})
    if login is not None:
        cf['Логин'] = {'value': login}
    return Lead(
        id=id,
        name=name,
        custom_fields_values=cf,
        status_id=status_id,
        _embedded={'contacts': contacts or []}
    )
