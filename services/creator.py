from typing import Optional

from crm.entities import Customer, Lead
from models import (
    db,
    AbstractCustomer,
    AmoCustomer,
    AmoLead,
    AmoCompany,
    AmoContact,
)


def create_or_update_customer(abstract_customer: Optional[AbstractCustomer], amo_customer: Customer) -> AbstractCustomer:
    """Создание или обновление покупателя в AbstractCustomer."""
    if abstract_customer is None:
        abstract_customer = AbstractCustomer()
        db.session.add(abstract_customer)
        db.session.flush()

    cf = amo_customer.custom_fields_values or {}
    login = cf.get('Логин', {}).get('value') if isinstance(cf.get('Логин'), dict) else cf.get('Логин')
    billing_type = cf.get('Вид оплаты', {}).get('value') if isinstance(cf.get('Вид оплаты'), dict) else cf.get('Вид оплаты')
    system = cf.get('Система', {}).get('value') if isinstance(cf.get('Система'), dict) else cf.get('Система')
    host = cf.get('Хост', {}).get('value') if isinstance(cf.get('Хост'), dict) else cf.get('Хост')
    api_val = amo_customer.as_dict() if hasattr(amo_customer, 'as_dict') else getattr(amo_customer, '__dict__', {})

    existing_cust = db.session.get(AmoCustomer, amo_customer.id)
    if existing_cust:
        existing_cust.abstract_customer_id = abstract_customer.id
        existing_cust.login = login
        existing_cust.name = amo_customer.name
        existing_cust.billing_type = billing_type
        existing_cust.is_robot = bool(cf.get('Робот'))
        existing_cust.is_nds = bool(cf.get('Оплата с НДС'))
        existing_cust.system = system
        existing_cust.host = host
        existing_cust.api_value = api_val
    else:
        new_cust = AmoCustomer(
            id=amo_customer.id,
            abstract_customer_id=abstract_customer.id,
            login=login,
            name=amo_customer.name,
            billing_type=billing_type,
            is_robot=bool(cf.get('Робот')),
            is_nds=bool(cf.get('Оплата с НДС')),
            system=system,
            host=host,
            api_value=api_val,
        )
        db.session.add(new_cust)

    for comp in getattr(amo_customer, 'companies', []):
        comp_id = comp.get('id') if isinstance(comp, dict) else getattr(comp, 'id', None)
        if comp_id:
            existing_comp = db.session.get(AmoCompany, comp_id)
            if existing_comp:
                existing_comp.abstract_customer_id = abstract_customer.id
            else:
                db.session.add(AmoCompany(
                    id=comp_id,
                    abstract_customer_id=abstract_customer.id,
                    name=comp.get('name') if isinstance(comp, dict) else getattr(comp, 'name', None),
                    inn=comp.get('inn') if isinstance(comp, dict) else getattr(comp, 'inn', None),
                    api_value=comp if isinstance(comp, dict) else getattr(comp, '__dict__', {})
                ))

    for cont in getattr(amo_customer, 'contacts', []):
        cont_id = cont.get('id') if isinstance(cont, dict) else getattr(cont, 'id', None)
        if cont_id:
            existing_cont = db.session.get(AmoContact, cont_id)
            if existing_cont:
                existing_cont.abstract_customer_id = abstract_customer.id
            else:
                db.session.add(AmoContact(
                    id=cont_id,
                    abstract_customer_id=abstract_customer.id,
                    name=cont.get('name') if isinstance(cont, dict) else getattr(cont, 'name', None),
                    phone=cont.get('phone') if isinstance(cont, dict) else getattr(cont, 'phone', None),
                    api_value=cont if isinstance(cont, dict) else getattr(cont, '__dict__', {})
                ))

    return abstract_customer


def create_or_update_lead(abc_customer: Optional[AbstractCustomer], amo_lead: Lead) -> AbstractCustomer:
    """Создание или обновление сделки в AbstractCustomer."""
    if abc_customer is None:
        abc_customer = AbstractCustomer()
        db.session.add(abc_customer)
        db.session.flush()

    cf = amo_lead.custom_fields_values or {}
    login = cf.get('Логин', {}).get('value') if isinstance(cf.get('Логин'), dict) else cf.get('Логин')
    api_val = amo_lead.as_dict() if hasattr(amo_lead, 'as_dict') else getattr(amo_lead, '__dict__', {})

    existing_lead = db.session.get(AmoLead, amo_lead.id)
    if existing_lead:
        existing_lead.abstract_customer_id = abc_customer.id
        existing_lead.login = login
        existing_lead.name = amo_lead.name
        existing_lead.api_value = api_val
    else:
        new_lead = AmoLead(
            id=amo_lead.id,
            abstract_customer_id=abc_customer.id,
            login=login,
            name=amo_lead.name,
            api_value=api_val,
        )
        db.session.add(new_lead)

    for cont in getattr(amo_lead, 'contacts', []):
        cont_id = cont.get('id') if isinstance(cont, dict) else getattr(cont, 'id', None)
        if cont_id:
            existing_cont = db.session.get(AmoContact, cont_id)
            if existing_cont:
                existing_cont.abstract_customer_id = abc_customer.id
            else:
                db.session.add(AmoContact(
                    id=cont_id,
                    abstract_customer_id=abc_customer.id,
                    name=cont.get('name') if isinstance(cont, dict) else getattr(cont, 'name', None),
                    phone=cont.get('phone') if isinstance(cont, dict) else getattr(cont, 'phone', None),
                    api_value=cont if isinstance(cont, dict) else getattr(cont, '__dict__', {})
                ))

    return abc_customer
