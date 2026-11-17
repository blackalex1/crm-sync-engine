from typing import Optional

from sqlalchemy import update, delete

from crm.entities import Lead
from models import (
    db,
    AbstractCustomer,
    AmoCustomer,
    AmoLead,
    AmoCompany,
    AmoContact
)


def lead_action(lead: Lead) -> AbstractCustomer:
    """
    Обработка отдельной сделки с соблюдением бизнес-логики:
    - Поиск по CRM id сделки, иначе по логину среди покупателей.
    - Если нашлись две разные записи — слияние в найденную по сделке, вторая удаляется.
    - Если не нашлось ничего — создаётся новая запись.
    - Обязательно возвращает целевой AbstractCustomer.
    """
    lead_login = lead.get_field('Логин')
    if lead_login:
        lead_login = str(lead_login).strip() or None

    # 1. Поиск по id сделки
    existing_lead = db.session.get(AmoLead, lead.id)
    target_ac: Optional[AbstractCustomer] = None
    if existing_lead:
        target_ac = db.session.get(AbstractCustomer, existing_lead.abstract_customer_id)

    # 2. Поиск по логину среди покупателей
    matched_cust: Optional[AmoCustomer] = None
    ac_by_cust_login: Optional[AbstractCustomer] = None
    if lead_login:
        custs = db.session.query(AmoCustomer).filter(AmoCustomer.login == lead_login).all()
        distinct_acs = {c.abstract_customer_id for c in custs}
        if len(distinct_acs) == 1:
            matched_cust = custs[0]
            ac_by_cust_login = db.session.get(AbstractCustomer, matched_cust.abstract_customer_id)

    # 3. Разрешение слияния и привязки
    if target_ac and ac_by_cust_login:
        if target_ac.id != ac_by_cust_login.id:
            # Слияние: всё из ac_by_cust_login переносим в target_ac, ac_by_cust_login удаляем
            source_id = ac_by_cust_login.id
            target_id = target_ac.id
            db.session.execute(
                update(AmoCustomer).where(AmoCustomer.abstract_customer_id == source_id)
                .values(abstract_customer_id=target_id)
            )
            db.session.execute(
                update(AmoLead).where(AmoLead.abstract_customer_id == source_id)
                .values(abstract_customer_id=target_id)
            )
            db.session.execute(
                update(AmoCompany).where(AmoCompany.abstract_customer_id == source_id)
                .values(abstract_customer_id=target_id)
            )
            db.session.execute(
                update(AmoContact).where(AmoContact.abstract_customer_id == source_id)
                .values(abstract_customer_id=target_id)
            )
            db.session.execute(
                delete(AbstractCustomer).where(AbstractCustomer.id == source_id)
            )
            db.session.flush()
    elif not target_ac and ac_by_cust_login:
        target_ac = ac_by_cust_login
    elif not target_ac and not ac_by_cust_login:
        # Ничего не нашлось — создаётся новая запись
        target_ac = AbstractCustomer()
        db.session.add(target_ac)
        db.session.flush()

    # 4. Обновление или создание AmoLead
    api_val = lead.as_dict() if hasattr(lead, 'as_dict') else getattr(lead, '__dict__', {})
    cust_id = matched_cust.id if matched_cust else (existing_lead.customer_id if existing_lead else None)

    if existing_lead:
        existing_lead.abstract_customer_id = target_ac.id
        existing_lead.customer_id = cust_id
        existing_lead.login = lead_login
        existing_lead.name = lead.name
        existing_lead.api_value = api_val
    else:
        new_lead = AmoLead(
            id=lead.id,
            abstract_customer_id=target_ac.id,
            customer_id=cust_id,
            login=lead_login,
            name=lead.name,
            api_value=api_val
        )
        db.session.add(new_lead)

    # Контакты сделки
    for cont in getattr(lead, 'contacts', []):
        cont_id = cont.get('id') if isinstance(cont, dict) else getattr(cont, 'id', None)
        if cont_id:
            existing_cont = db.session.get(AmoContact, cont_id)
            if existing_cont:
                existing_cont.abstract_customer_id = target_ac.id
            else:
                db.session.add(AmoContact(
                    id=cont_id,
                    abstract_customer_id=target_ac.id,
                    name=cont.get('name') if isinstance(cont, dict) else getattr(cont, 'name', None),
                    phone=cont.get('phone') if isinstance(cont, dict) else getattr(cont, 'phone', None),
                    api_value=cont if isinstance(cont, dict) else getattr(cont, '__dict__', {})
                ))

    db.session.flush()
    return target_ac
