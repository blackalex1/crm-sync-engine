import logging
from typing import Optional

from models import db, AbstractCustomer, AmoCustomer, AmoLead

logger = logging.getLogger(__name__)


def get_abccustomer_by_lead_login(lead_login: str) -> Optional[AbstractCustomer]:
    """
    Поиск AbstractCustomer по логину сделки.
    Если нашлось больше одной записи, совпадение не используется (возвращает None).
    """
    if not lead_login:
        return None

    leads = db.session.query(AmoLead).filter(AmoLead.login == lead_login).all()
    if not leads:
        return None

    distinct_ac_ids = {l.abstract_customer_id for l in leads}
    if len(distinct_ac_ids) > 1:
        logger.warning(f"Lead {lead_login} has more than one abccustomer: {distinct_ac_ids}")
        return None

    ac_id = next(iter(distinct_ac_ids))
    return db.session.get(AbstractCustomer, ac_id)


def get_abccustomer_by_amocustomer_login(customer_login: str) -> Optional[AbstractCustomer]:
    """
    Поиск AbstractCustomer по логину покупателя.
    Если нашлось больше одной записи, совпадение не используется (возвращает None).
    """
    if not customer_login:
        return None

    customers = db.session.query(AmoCustomer).filter(AmoCustomer.login == customer_login).all()
    if not customers:
        return None

    distinct_ac_ids = {c.abstract_customer_id for c in customers}
    if len(distinct_ac_ids) > 1:
        logger.warning(f"Customer {customer_login} has more than one abccustomer: {distinct_ac_ids}")
        return None

    ac_id = next(iter(distinct_ac_ids))
    return db.session.get(AbstractCustomer, ac_id)
