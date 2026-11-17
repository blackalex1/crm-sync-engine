import logging
from collections import defaultdict
from typing import List, Dict, Optional, Tuple

from sqlalchemy import insert, text

from crm.entities import Customer
from models import (
    AbstractCustomer,
    AmoCustomer,
    AmoCompany,
    AmoContact,
    AmoLead
)
from sync.upsert import bulk_upsert

logger = logging.getLogger(__name__)


def sync_customers_batch(
    session,
    batch: List[Customer],
    sync_run_id: str,
    is_full: bool = True,
    customer_login_cache: Optional[Dict[str, Optional[Tuple[int, int]]]] = None
):
    """Пакетная синхронизация пачки покупателей с CRM в БД."""
    valid_customers: List[Customer] = []
    for c in batch:
        if not is_full and c.status_id == 111349:
            continue
        c_login = c.get_field('Логин')
        if not c_login or not str(c_login).strip():
            continue
        valid_customers.append(c)

    if not valid_customers:
        return

    cust_ids = [c.id for c in valid_customers]

    # 1. Поиск существующих покупателей в БД по CRM ID
    existing_cust_rows = session.query(
        AmoCustomer.id, AmoCustomer.abstract_customer_id
    ).filter(AmoCustomer.id.in_(cust_ids)).all()
    existing_cust_map: Dict[int, int] = {row[0]: row[1] for row in existing_cust_rows}

    # 2. Для покупателей, не найденных по ID, ищем по логину среди сделок
    missing_customers = [c for c in valid_customers if c.id not in existing_cust_map]
    login_to_ac_map: Dict[str, Optional[int]] = {}

    if missing_customers:
        missing_logins = list({str(c.get_field('Логин')).strip() for c in missing_customers})
        lead_rows = session.query(
            AmoLead.login, AmoLead.abstract_customer_id
        ).filter(AmoLead.login.in_(missing_logins)).all()

        login_groups: Dict[str, set] = defaultdict(set)
        for l_login, l_ac_id in lead_rows:
            login_groups[l_login].add(l_ac_id)

        for l_login, ac_set in login_groups.items():
            # Правило: если по логину нашлось больше одной записи, совпадение не используется
            if len(ac_set) == 1:
                login_to_ac_map[l_login] = next(iter(ac_set))
            else:
                login_to_ac_map[l_login] = None

    # 3. Назначение AbstractCustomer (существующий или новый)
    new_ac_needed_count = 0
    for c in valid_customers:
        if c.id not in existing_cust_map:
            c_login = str(c.get_field('Логин')).strip()
            matched_ac = login_to_ac_map.get(c_login)
            if not matched_ac:
                new_ac_needed_count += 1

    if new_ac_needed_count > 0:
        bind = session.get_bind()
        if bind and bind.dialect.name == 'postgresql':
            res = session.execute(
                text(f"INSERT INTO abstract_customer (send_methods) SELECT '[]'::jsonb FROM generate_series(1, {new_ac_needed_count}) RETURNING id;")
            )
            new_ac_ids = [row[0] for row in res.fetchall()]
        else:
            res = session.execute(
                insert(AbstractCustomer)
                .values([{'send_methods': []} for _ in range(new_ac_needed_count)])
                .returning(AbstractCustomer.id)
            )
            new_ac_ids = [row[0] for row in res.fetchall()]
        new_ac_iter = iter(new_ac_ids)
    else:
        new_ac_iter = iter([])

    cust_records: List[Dict] = []
    comp_records: List[Dict] = []
    cont_records: List[Dict] = []

    for c in valid_customers:
        c_login = str(c.get_field('Логин')).strip()
        if c.id in existing_cust_map:
            target_ac_id = existing_cust_map[c.id]
        else:
            matched_ac = login_to_ac_map.get(c_login)
            if matched_ac:
                target_ac_id = matched_ac
                existing_cust_map[c.id] = target_ac_id
            else:
                target_ac_id = next(new_ac_iter)
                existing_cust_map[c.id] = target_ac_id

        # Сохранение в in-memory кэш для фазы сделок
        if customer_login_cache is not None:
            if c_login in customer_login_cache:
                prev = customer_login_cache[c_login]
                if prev and prev[1] != target_ac_id:
                    customer_login_cache[c_login] = None  # Неоднозначное совпадение
            else:
                customer_login_cache[c_login] = (c.id, target_ac_id)

        cf = c.custom_fields_values or {}
        billing_type = cf.get('Вид оплаты', {}).get('value') if isinstance(cf.get('Вид оплаты'), dict) else cf.get('Вид оплаты')
        system = cf.get('Система', {}).get('value') if isinstance(cf.get('Система'), dict) else cf.get('Система')
        host = cf.get('Хост', {}).get('value') if isinstance(cf.get('Хост'), dict) else cf.get('Хост')
        api_val = c.as_dict() if hasattr(c, 'as_dict') else getattr(c, '__dict__', {})

        cust_records.append({
            'id': c.id,
            'abstract_customer_id': target_ac_id,
            'login': c_login,
            'name': c.name,
            'billing_type': billing_type,
            'is_robot': bool(cf.get('Робот')),
            'is_nds': bool(cf.get('Оплата с НДС')),
            'system': system,
            'host': host,
            'api_value': api_val,
            'sync_run_id': sync_run_id
        })

        for comp in getattr(c, 'companies', []):
            comp_id = comp.get('id') if isinstance(comp, dict) else getattr(comp, 'id', None)
            if comp_id:
                comp_records.append({
                    'id': comp_id,
                    'abstract_customer_id': target_ac_id,
                    'name': comp.get('name') if isinstance(comp, dict) else getattr(comp, 'name', None),
                    'inn': comp.get('inn') if isinstance(comp, dict) else getattr(comp, 'inn', None),
                    'api_value': comp if isinstance(comp, dict) else getattr(comp, '__dict__', {}),
                    'sync_run_id': sync_run_id
                })

        for cont in getattr(c, 'contacts', []):
            cont_id = cont.get('id') if isinstance(cont, dict) else getattr(cont, 'id', None)
            if cont_id:
                cont_records.append({
                    'id': cont_id,
                    'abstract_customer_id': target_ac_id,
                    'name': cont.get('name') if isinstance(cont, dict) else getattr(cont, 'name', None),
                    'phone': cont.get('phone') if isinstance(cont, dict) else getattr(cont, 'phone', None),
                    'api_value': cont if isinstance(cont, dict) else getattr(cont, '__dict__', {}),
                    'sync_run_id': sync_run_id
                })

    # 4. Пакетный UPSERT покупателей, компаний и контактов
    bulk_upsert(session, AmoCustomer, cust_records, [
        'abstract_customer_id', 'login', 'name', 'billing_type',
        'is_robot', 'is_nds', 'system', 'host', 'api_value', 'sync_run_id'
    ])
    bulk_upsert(session, AmoCompany, comp_records, [
        'abstract_customer_id', 'name', 'inn', 'api_value', 'sync_run_id'
    ])
    bulk_upsert(session, AmoContact, cont_records, [
        'abstract_customer_id', 'name', 'phone', 'api_value', 'sync_run_id'
    ])
