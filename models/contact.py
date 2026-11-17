from sqlalchemy import Column, func
from sqlalchemy.orm import relationship

from models.base import db, JSON_TYPE


class AmoContact(db.Model):
    """Модель контакта amoCRM."""
    __tablename__ = "amo_contact"

    id = Column(db.BigInteger(), primary_key=True)  # CRM Contact ID
    abstract_customer_id = Column(
        db.BigInteger(),
        db.ForeignKey('abstract_customer.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    name = Column(db.String(255), index=True, nullable=True)
    phone = Column(db.String(64), nullable=True)
    api_value = Column(JSON_TYPE, nullable=True, default=dict)
    sync_run_id = Column(db.String(64), index=True, nullable=True)
    created_at = Column(db.DateTime, server_default=func.now())
    updated_at = Column(db.DateTime, onupdate=func.now())

    abstract_customer = relationship('AbstractCustomer', back_populates='contacts')

    def to_json(self):
        return {
            'general': {
                'id': self.id,
                'name': self.name,
                'phone': self.phone,
            },
            'api_value': self.api_value or {}
        }

    def __repr__(self):
        return f"<AmoContact id={self.id} name={self.name}>"
