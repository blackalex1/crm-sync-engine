from sqlalchemy import Column, func
from sqlalchemy.orm import relationship

from models.base import db, JSON_TYPE


class AmoCustomer(db.Model):
    """Модель покупателя amoCRM."""
    __tablename__ = "amo_customer"

    id = Column(db.BigInteger(), primary_key=True)  # CRM Customer ID
    abstract_customer_id = Column(
        db.BigInteger(),
        db.ForeignKey('abstract_customer.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    login = Column(db.String(255), index=True, nullable=True)
    name = Column(db.String(255), index=True, nullable=True)
    billing_type = Column(db.String(255), nullable=True)
    is_robot = Column(db.Boolean, default=False, nullable=True)
    is_nds = Column(db.Boolean, default=False, nullable=True)
    system = Column(db.String(255), nullable=True)
    host = Column(db.String(255), nullable=True)
    api_value = Column(JSON_TYPE, nullable=True, default=dict)
    sync_run_id = Column(db.String(64), index=True, nullable=True)
    created_at = Column(db.DateTime, server_default=func.now())
    updated_at = Column(db.DateTime, onupdate=func.now())

    abstract_customer = relationship('AbstractCustomer', back_populates='customers')
    leads = relationship('AmoLead', back_populates='customer')

    def to_json(self):
        return {
            'general': {
                'id': self.id,
                'login': self.login,
                'billing_type': self.billing_type,
                'is_robot': bool(self.is_robot),
                'is_nds': bool(self.is_nds),
                'system': self.system,
                'host': self.host,
                'name': self.name,
            },
            'api_value': self.api_value or {}
        }

    def __repr__(self):
        return f"<AmoCustomer id={self.id} login={self.login}>"
