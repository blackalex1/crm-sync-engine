"""
Главная точка входа приложения и ночной синхронизации CRM.
Точка входа — collect_leads_customers(is_full=True).
"""
from sync import collect_leads_customers
from services import lead_action
from crm import Customer, Lead, amocrm_get
from models import (
    db,
    AbstractCustomer,
    AmoCustomer,
    AmoLead,
    AmoCompany,
    AmoContact,
)

__all__ = [
    'collect_leads_customers',
    'lead_action',
    'Customer',
    'Lead',
    'amocrm_get',
    'db',
    'AbstractCustomer',
    'AmoCustomer',
    'AmoLead',
    'AmoCompany',
    'AmoContact',
]
