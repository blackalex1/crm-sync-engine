from crm.entities import Customer, Lead


def get_customer_json(customer: Customer) -> dict:
    cf = customer.custom_fields_values or {}
    api_val = customer.as_dict() if hasattr(customer, 'as_dict') else getattr(customer, '__dict__', {})
    return {
        'general': {
            'id': customer.id,
            'login': cf.get('Логин', {}).get('value') if isinstance(cf.get('Логин'), dict) else cf.get('Логин'),
            'billing_type': cf.get('Вид оплаты', {}).get('value') if isinstance(cf.get('Вид оплаты'), dict) else cf.get('Вид оплаты'),
            'is_robot': bool(cf.get('Робот')),
            'is_nds': bool(cf.get('Оплата с НДС')),
            'system': cf.get('Система', {}).get('value') if isinstance(cf.get('Система'), dict) else cf.get('Система'),
            'host': cf.get('Хост', {}).get('value') if isinstance(cf.get('Хост'), dict) else cf.get('Хост'),
            'name': customer.name,
        },
        'api_value': api_val
    }


def get_lead_json(lead: Lead) -> dict:
    cf = lead.custom_fields_values or {}
    api_val = lead.as_dict() if hasattr(lead, 'as_dict') else getattr(lead, '__dict__', {})
    return {
        'general': {
            'id': lead.id,
            'login': cf.get('Логин', {}).get('value') if isinstance(cf.get('Логин'), dict) else cf.get('Логин'),
            'name': lead.name,
        },
        'api_value': api_val
    }
