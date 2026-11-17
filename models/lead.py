from sqlalchemy import Column, func
from sqlalchemy.orm import relationship

from models.base import db, JSON_TYPE


class AmoLead(db.Model):
    """Модель сделки amoCRM."""
    __tablename__ = "amo_lead"

    id = Column(db.BigInteger(), primary_key=True)  # CRM Lead ID
    abstract_customer_id = Column(
        db.BigInteger(),
        db.ForeignKey('abstract_customer.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    customer_id = Column(
        db.BigInteger(),
        db.ForeignKey('amo_customer.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    login = Column(db.String(255), index=True, nullable=True)
    name = Column(db.String(255), index=True, nullable=True)
    api_value = Column(JSON_TYPE, nullable=True, default=dict)
    sync_run_id = Column(db.String(64), index=True, nullable=True)
    created_at = Column(db.DateTime, server_default=func.now())
    updated_at = Column(db.DateTime, onupdate=func.now())

    abstract_customer = relationship('AbstractCustomer', back_populates='leads')
    customer = relationship('AmoCustomer', back_populates='leads')

    def to_json(self):
        return {
            'general': {
                'id': self.id,
                'login': self.login,
                'name': self.name,
            },
            'api_value': self.api_value or {}
        }

    def __repr__(self):
        return f"<AmoLead id={self.id} login={self.login}>"
