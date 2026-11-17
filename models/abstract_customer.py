from sqlalchemy import Column, func
from sqlalchemy.orm import relationship

from models.base import db, JSON_TYPE
from models.customer import AmoCustomer
from models.lead import AmoLead
from models.company import AmoCompany
from models.contact import AmoContact


class AbstractCustomer(db.Model):
    """
    Агрегирующая сущность покупателя, связывающая в единый профиль
    покупателей amoCRM, сделки, компании и контакты.
    """
    __tablename__ = "abstract_customer"

    id = Column(db.BigInteger().with_variant(db.Integer, 'sqlite'), primary_key=True, autoincrement=True)
    send_methods = Column(JSON_TYPE, nullable=True, default=list)
    created_at = Column(db.DateTime, server_default=func.now())
    updated_at = Column(db.DateTime, onupdate=func.now())

    customers = relationship(
        'AmoCustomer',
        back_populates='abstract_customer',
        cascade='all, delete-orphan',
        lazy='selectin'
    )
    leads = relationship(
        'AmoLead',
        back_populates='abstract_customer',
        cascade='all, delete-orphan',
        lazy='selectin'
    )
    companies = relationship(
        'AmoCompany',
        back_populates='abstract_customer',
        cascade='all, delete-orphan',
        lazy='selectin'
    )
    contacts = relationship(
        'AmoContact',
        back_populates='abstract_customer',
        cascade='all, delete-orphan',
        lazy='selectin'
    )

    @property
    def amo_customers(self):
        return [c.to_json() for c in self.customers]

    @property
    def amo_leads(self):
        return [l.to_json() for l in self.leads]

    @property
    def amo_companies(self):
        return [comp.to_json() for comp in self.companies]

    @property
    def amo_contacts(self):
        return [cont.to_json() for cont in self.contacts]

    def __repr__(self):
        return f"<AbstractCustomer id={self.id}>"
