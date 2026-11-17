import logging
from collections import defaultdict
from typing import List, Dict, Optional, Tuple

from sqlalchemy import insert, update, delete, text

from crm.entities import Lead
from models import (
    AbstractCustomer,
    AmoCustomer,
    AmoLead,
    AmoCompany,
    AmoContact
)
from sync.upsert import bulk_upsert

logger = logging.getLogger(__name__)


def sync_leads_batch(
    session,
    batch: List[Lead],
    sync_run_id: str,
    is_full: bool = True,
    customer_login_cache: Optional[Dict[str, Optional[Tuple[int, int]]]] = None
):
    """Пакетная синхронизация пачки сделок с CRM в БД."""
    valid_leads: List[Lead] = []
    for l in batch:
        if not is_full and l.status_id == 143:
            continue
        valid_leads.append(l)

    if not valid_leads:
        return

    lead_ids = [l.id for l in valid_leads]

    # 1. Поиск существующих сделок в БД по CRM ID
    existing_lead_rows = session.query(
        AmoLead.id, AmoLead.abstract_customer_id, AmoLead.customer_id
    ).filter(AmoLead.id.in_(lead_ids)).all()
    existing_lead_map: Dict[int, Tuple[int, Optional[int]]] = {
        row[0]: (row[1], row[2]) for row in existing_lead_rows
    }

    # 2. Поиск по логину среди покупателей
    logins_to_check = list({
        str(l.get_field('Логин')).strip() for l in valid_leads
        if l.get_field('Логин') and str(l.get_field('Логин')).strip()
    })
    customer_login_map: Dict[str, Optional[Tuple[int, int]]] = {}

    logins_needing_db: List[str] = []
    if logins_to_check:
        if customer_login_cache is not None:
            for l_login in logins_to_check:
                if l_login in customer_login_cache:
                    customer_login_map[l_login] = customer_login_cache[l_login]
                else:
                    logins_needing_db.append(l_login)
        else:
            logins_needing_db = logins_to_check

    if logins_needing_db:
        cust_rows = session.query(
            AmoCustomer.login, AmoCustomer.id, AmoCustomer.abstract_customer_id
        ).filter(AmoCustomer.login.in_(logins_needing_db)).all()

        cust_groups: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        for c_login, c_id, c_ac_id in cust_rows:
            cust_groups[c_login].append((c_id, c_ac_id))

        for c_login, c_list in cust_groups.items():
            distinct_acs = {ac_id for _, ac_id in c_list}
            if len(distinct_acs) == 1:
                customer_login_map[c_login] = c_list[0]
            else:
                customer_login_map[c_login] = None

    # 3. Обработка правил поиска, слияния и создания
    ac_redirect: Dict[int, int] = {}

    def get_effective_ac(ac_id: Optional[int]) -> Optional[int]:
        while ac_id in ac_redirect:
            ac_id = ac_redirect[ac_id]
        return ac_id

    leads_to_create_ac = []
    resolved_leads: List[Tuple[Lead, Optional[int], Optional[int]]] = []
    merges_to_apply: List[Tuple[int, int]] = []

    for l in valid_leads:
        l_login = str(l.get_field('Логин')).strip() if l.get_field('Логин') else None
        if l_login == '':
            l_login = None

        lead_match = existing_lead_map.get(l.id)
        ac_by_lead = get_effective_ac(lead_match[0]) if lead_match else None
        existing_cust_link = lead_match[1] if lead_match else None

        cust_match = customer_login_map.get(l_login) if l_login else None
        ac_by_cust = get_effective_ac(cust_match[1]) if cust_match else None
        matched_cust_id = cust_match[0] if cust_match else None

        if ac_by_lead and ac_by_cust:
            if ac_by_lead != ac_by_cust:
                # Слияние: сущности из ac_by_cust переходят в ac_by_lead, ac_by_cust удаляется
                source_id = ac_by_cust
                target_id = ac_by_lead
                merges_to_apply.append((source_id, target_id))
                ac_redirect[source_id] = target_id

            target_ac_id = ac_by_lead
            cust_link = matched_cust_id or existing_cust_link
        elif ac_by_lead and not ac_by_cust:
            target_ac_id = ac_by_lead
            cust_link = existing_cust_link
        elif not ac_by_lead and ac_by_cust:
            target_ac_id = ac_by_cust
            cust_link = matched_cust_id
        else:
            # Ничего не нашлось — создаётся новая запись
            target_ac_id = None
            cust_link = None
            leads_to_create_ac.append(l)

        resolved_leads.append((l, target_ac_id, cust_link))

    # Выполнение накопленных слияний
    if merges_to_apply:
        for source_id, target_id in merges_to_apply:
            session.execute(
                update(AmoCustomer).where(AmoCustomer.abstract_customer_id == source_id)
                .values(abstract_customer_id=target_id)
            )
            session.execute(
                update(AmoLead).where(AmoLead.abstract_customer_id == source_id)
                .values(abstract_customer_id=target_id)
            )
            session.execute(
                update(AmoCompany).where(AmoCompany.abstract_customer_id == source_id)
                .values(abstract_customer_id=target_id)
            )
            session.execute(
                update(AmoContact).where(AmoContact.abstract_customer_id == source_id)
                .values(abstract_customer_id=target_id)
            )
            session.execute(
                delete(AbstractCustomer).where(AbstractCustomer.id == source_id)
            )
        session.flush()

    # Создание новых AbstractCustomer для ненайденных сделок
    if leads_to_create_ac:
        bind = session.get_bind()
        count = len(leads_to_create_ac)
        if bind and bind.dialect.name == 'postgresql':
            res = session.execute(
                text(f"INSERT INTO abstract_customer (send_methods) SELECT '[]'::jsonb FROM generate_series(1, {count}) RETURNING id;")
            )
            new_ac_ids = [row[0] for row in res.fetchall()]
        else:
            res = session.execute(
                insert(AbstractCustomer)
                .values([{'send_methods': []} for _ in leads_to_create_ac])
                .returning(AbstractCustomer.id)
            )
            new_ac_ids = [row[0] for row in res.fetchall()]
        new_ac_iter = iter(new_ac_ids)
    else:
        new_ac_iter = iter([])

    lead_records: List[Dict] = []
    cont_records: List[Dict] = []

    for l, target_ac_id, cust_link in resolved_leads:
        if target_ac_id is None:
            target_ac_id = next(new_ac_iter)

        l_login = str(l.get_field('Логин')).strip() if l.get_field('Логин') else None
        api_val = l.as_dict() if hasattr(l, 'as_dict') else getattr(l, '__dict__', {})

        lead_records.append({
            'id': l.id,
            'abstract_customer_id': target_ac_id,
            'customer_id': cust_link,
            'login': l_login,
            'name': l.name,
            'api_value': api_val,
            'sync_run_id': sync_run_id
        })

        for cont in getattr(l, 'contacts', []):
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

    # 4. Пакетный UPSERT сделок и контактов
    bulk_upsert(session, AmoLead, lead_records, [
        'abstract_customer_id', 'customer_id', 'login', 'name', 'api_value', 'sync_run_id'
    ])
    bulk_upsert(session, AmoContact, cont_records, [
        'abstract_customer_id', 'name', 'phone', 'api_value', 'sync_run_id'
    ])
