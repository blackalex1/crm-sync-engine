from sqlalchemy import Column, func
from sqlalchemy.orm import relationship

from models.base import db, JSON_TYPE


class AmoCompany(db.Model):
    """Модель компании amoCRM."""
    __tablename__ = "amo_company"

    id = Column(db.BigInteger(), primary_key=True)  # CRM Company ID
    abstract_customer_id = Column(
        db.BigInteger(),
        db.ForeignKey('abstract_customer.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    name = Column(db.String(255), index=True, nullable=True)
    inn = Column(db.String(64), nullable=True)
    api_value = Column(JSON_TYPE, nullable=True, default=dict)
    sync_run_id = Column(db.String(64), index=True, nullable=True)
    created_at = Column(db.DateTime, server_default=func.now())
    updated_at = Column(db.DateTime, onupdate=func.now())

    abstract_customer = relationship('AbstractCustomer', back_populates='companies')

    def to_json(self):
        return {
            'general': {
                'id': self.id,
                'name': self.name,
                'inn': self.inn,
            },
            'api_value': self.api_value or {}
        }

    def __repr__(self):
        return f"<AmoCompany id={self.id} name={self.name}>"
