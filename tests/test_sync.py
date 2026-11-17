import pytest
from unittest.mock import patch

from models import db, AbstractCustomer, AmoCustomer, AmoLead, AmoCompany, AmoContact
from main import collect_leads_customers, lead_action
from tests.conftest import make_customer, make_lead


def test_customer_without_login_is_skipped(session):
    """Покупатель без логина пропускается."""
    customers = [
        make_customer(1, name='No Login', login=None),
        make_customer(2, name='Empty Login', login=''),
        make_customer(3, name='Whitespace Login', login='   '),
        make_customer(4, name='Valid Customer', login='valid_user'),
    ]
    leads = []

    with patch('main.amocrm_get', side_effect=[iter(customers), iter(leads)]):
        collect_leads_customers(is_full=True)

    saved_custs = session.query(AmoCustomer).all()
    assert len(saved_custs) == 1
    assert saved_custs[0].id == 4
    assert saved_custs[0].login == 'valid_user'


def test_customer_search_by_crm_id(session):
    """Покупатель ищется по id покупателя в CRM и обновляется."""
    ac = AbstractCustomer()
    session.add(ac)
    session.flush()

    old_cust = AmoCustomer(
        id=10,
        abstract_customer_id=ac.id,
        login='old_login',
        name='Old Name'
    )
    session.add(old_cust)
    session.commit()

    updated_cust = make_customer(10, name='New Name', login='new_login')

    with patch('main.amocrm_get', side_effect=[iter([updated_cust]), iter([])]):
        collect_leads_customers(is_full=True)

    db_cust = session.get(AmoCustomer, 10)
    assert db_cust is not None
    assert db_cust.name == 'New Name'
    assert db_cust.login == 'new_login'
    assert db_cust.abstract_customer_id == ac.id


def test_customer_search_by_lead_login(session):
    """Покупатель не найден по ID, но найден по логину среди уже сохранённых сделок."""
    ac = AbstractCustomer()
    session.add(ac)
    session.flush()

    lead = AmoLead(
        id=55,
        abstract_customer_id=ac.id,
        login='target_login',
        name='Existing Lead'
    )
    session.add(lead)
    session.commit()

    new_customer = make_customer(100, name='Matching Cust', login='target_login')

    with patch('main.amocrm_get', side_effect=[iter([new_customer]), iter([])]):
        collect_leads_customers(is_full=True)

    db_cust = session.get(AmoCustomer, 100)
    assert db_cust is not None
    assert db_cust.abstract_customer_id == ac.id


def test_customer_search_by_lead_login_ambiguous(session):
    """Если по логину нашлось больше одной записи, совпадение не используется."""
    ac1 = AbstractCustomer()
    ac2 = AbstractCustomer()
    session.add_all([ac1, ac2])
    session.flush()
    ac1_id = ac1.id
    ac2_id = ac2.id
    ac1_id = ac1.id
    ac2_id = ac2.id

    # Две сделки в разных AbstractCustomer с одним логином
    lead1 = AmoLead(id=1, abstract_customer_id=ac1_id, login='ambiguous_login', name='Lead 1')
    lead2 = AmoLead(id=2, abstract_customer_id=ac2_id, login='ambiguous_login', name='Lead 2')
    session.add_all([lead1, lead2])
    session.commit()

    new_cust = make_customer(200, name='Ambiguous Cust', login='ambiguous_login')

    with patch('main.amocrm_get', side_effect=[iter([new_cust]), iter([])]):
        collect_leads_customers(is_full=True)

    db_cust = session.get(AmoCustomer, 200)
    assert db_cust is not None
    # Должен быть создан НОВЫЙ AbstractCustomer, а не привязан к ac1 или ac2
    assert db_cust.abstract_customer_id != ac1_id
    assert db_cust.abstract_customer_id != ac2_id


def test_lead_search_by_crm_id(session):
    """Сделка ищется по id сделки в CRM."""
    ac = AbstractCustomer()
    session.add(ac)
    session.flush()

    old_lead = AmoLead(id=77, abstract_customer_id=ac.id, login='lead_login', name='Old Lead Name')
    session.add(old_lead)
    session.commit()

    updated_lead = make_lead(77, name='Updated Lead Name', login='lead_login')

    with patch('main.amocrm_get', side_effect=[iter([]), iter([updated_lead])]):
        collect_leads_customers(is_full=True)

    db_lead = session.get(AmoLead, 77)
    assert db_lead is not None
    assert db_lead.name == 'Updated Lead Name'
    assert db_lead.abstract_customer_id == ac.id


def test_lead_search_by_customer_login(session):
    """Сделка ищется по логину среди покупателей, если не найдена по ID."""
    ac = AbstractCustomer()
    session.add(ac)
    session.flush()

    cust = AmoCustomer(id=15, abstract_customer_id=ac.id, login='buyer_login', name='Buyer')
    session.add(cust)
    session.commit()

    new_lead = make_lead(88, name='New Deal', login='buyer_login')

    with patch('main.amocrm_get', side_effect=[iter([make_customer(15, name='Buyer', login='buyer_login')]), iter([new_lead])]):
        collect_leads_customers(is_full=True)

    db_lead = session.get(AmoLead, 88)
    assert db_lead is not None
    assert db_lead.abstract_customer_id == ac.id
    assert db_lead.customer_id == cust.id


def test_lead_merge_two_different_records(session):
    """
    Если сделка найдена по id в одной записи, а по логину среди покупателей в другой —
    они сливаются в ту, что нашли по сделке; вторая удаляется.
    """
    # AC1: содержит сделку 99
    ac1 = AbstractCustomer()
    # AC2: содержит покупателя с логином 'shared_login'
    ac2 = AbstractCustomer()
    session.add_all([ac1, ac2])
    session.flush()
    ac1_id = ac1.id
    ac2_id = ac2.id

    lead_in_ac1 = AmoLead(id=99, abstract_customer_id=ac1_id, name='Existing Lead 99')
    cust_in_ac2 = AmoCustomer(id=30, abstract_customer_id=ac2_id, login='shared_login', name='Customer 30')
    comp_in_ac2 = AmoCompany(id=40, abstract_customer_id=ac2_id, name='Company 40')
    cont_in_ac2 = AmoContact(id=50, abstract_customer_id=ac2_id, name='Contact 50')

    session.add_all([lead_in_ac1, cust_in_ac2, comp_in_ac2, cont_in_ac2])
    session.commit()

    # Приходит сделка 99 с логином 'shared_login'
    incoming_lead = make_lead(99, name='Incoming Lead 99', login='shared_login')
    incoming_cust = make_customer(
        30,
        name='Customer 30',
        login='shared_login',
        companies=[{'id': 40, 'name': 'Company 40'}],
        contacts=[{'id': 50, 'name': 'Contact 50'}]
    )

    with patch('main.amocrm_get', side_effect=[iter([incoming_cust]), iter([incoming_lead])]):
        collect_leads_customers(is_full=True)

    # ac2 должен быть удалён
    assert session.get(AbstractCustomer, ac2_id) is None
    # ac1 должен существовать
    assert session.get(AbstractCustomer, ac1_id) is not None

    # Все сущности из ac2 должны переместиться в ac1
    db_cust = session.get(AmoCustomer, 30)
    assert db_cust.abstract_customer_id == ac1_id

    db_comp = session.get(AmoCompany, 40)
    assert db_comp.abstract_customer_id == ac1_id

    db_cont = session.get(AmoContact, 50)
    assert db_cont.abstract_customer_id == ac1_id

    db_lead = session.get(AmoLead, 99)
    assert db_lead.abstract_customer_id == ac1_id
    assert db_lead.customer_id == 30


def test_lead_created_when_nothing_found(session):
    """Если не нашлось ничего, создаётся новая запись."""
    lead = make_lead(123, name='Brand New Deal', login='brand_new_user')

    with patch('main.amocrm_get', side_effect=[iter([]), iter([lead])]):
        collect_leads_customers(is_full=True)

    db_lead = session.get(AmoLead, 123)
    assert db_lead is not None
    assert db_lead.abstract_customer_id is not None
    ac = session.get(AbstractCustomer, db_lead.abstract_customer_id)
    assert ac is not None


def test_cleanup_deletes_unseen_and_marked_entities(session):
    """
    После успешного полного прохода удаляются покупатели и вложенные сущности,
    которых не было в этой выгрузке, в том числе с «удалить» в имени.
    """
    ac1 = AbstractCustomer()
    ac2 = AbstractCustomer()
    session.add_all([ac1, ac2])
    session.flush()
    ac1_id = ac1.id
    ac2_id = ac2.id

    # Сущности, которых не будет в выгрузке (должны удалиться)
    old_cust = AmoCustomer(id=1, abstract_customer_id=ac1.id, login='old1', name='Old Cust')
    old_lead = AmoLead(id=1, abstract_customer_id=ac1.id, login='old1', name='Old Lead')
    old_comp = AmoCompany(id=1, abstract_customer_id=ac1.id, name='Old Company')
    old_cont = AmoContact(id=1, abstract_customer_id=ac1.id, name='Old Contact')

    # Сущности в выгрузке, но содержащие 'удалить' в имени (должны удалиться)
    del_cust = AmoCustomer(id=2, abstract_customer_id=ac2.id, login='del_cust', name='Покупатель УДАЛИТЬ')
    del_lead = AmoLead(id=2, abstract_customer_id=ac2.id, login='del_lead', name='Сделка удалить')

    # Валидная сущность в выгрузке
    keep_cust = AmoCustomer(id=3, abstract_customer_id=ac2.id, login='keep_user', name='Keep Customer')

    session.add_all([old_cust, old_lead, old_comp, old_cont, del_cust, del_lead, keep_cust])
    session.commit()

    # В новой выгрузке: только cust 2, cust 3, lead 2
    incoming_custs = [
        make_customer(2, name='Покупатель УДАЛИТЬ', login='del_cust'),
        make_customer(3, name='Keep Customer', login='keep_user'),
    ]
    incoming_leads = [
        make_lead(2, name='Сделка удалить', login='del_lead')
    ]

    with patch('main.amocrm_get', side_effect=[iter(incoming_custs), iter(incoming_leads)]):
        collect_leads_customers(is_full=True)

    # 1. Отсутствующие в выгрузке — удалены
    assert session.get(AmoCustomer, 1) is None
    assert session.get(AmoLead, 1) is None
    assert session.get(AmoCompany, 1) is None
    assert session.get(AmoContact, 1) is None

    # 2. Содержащие 'удалить' — удалены
    assert session.get(AmoCustomer, 2) is None
    assert session.get(AmoLead, 2) is None

    # 3. Валидный покупатель — сохранён
    assert session.get(AmoCustomer, 3) is not None

    # 4. ac1 остался без покупателей и без сделок — удалён
    assert session.get(AbstractCustomer, ac1_id) is None

    # 5. ac2 содержит cust 3 — сохранён
    assert session.get(AbstractCustomer, ac2_id) is not None


def test_interrupted_collection_does_not_run_cleanup(session):
    """Если сбор прервался, удаление не запускается."""
    ac = AbstractCustomer()
    session.add(ac)
    session.flush()

    existing_cust = AmoCustomer(id=500, abstract_customer_id=ac.id, login='safe_user', name='Safe Customer')
    session.add(existing_cust)
    session.commit()

    def failing_leads():
        raise RuntimeError("CRM API connection lost!")

    with pytest.raises(RuntimeError):
        with patch('main.amocrm_get', side_effect=[iter([]), failing_leads()]):
            collect_leads_customers(is_full=True)

    # Существующий покупатель НЕ должен быть удален!
    db_cust = session.get(AmoCustomer, 500)
    assert db_cust is not None
    assert db_cust.name == 'Safe Customer'


def test_is_full_false_behavior(session):
    """
    При is_full=False:
    - Покупатели со status_id == 111349 пропускаются.
    - Сделки со status_id == 143 пропускаются.
    - Очистка не запускается.
    """
    ac = AbstractCustomer()
    session.add(ac)
    session.flush()

    existing_cust = AmoCustomer(id=999, abstract_customer_id=ac.id, login='old_user', name='Old Active Customer')
    session.add(existing_cust)
    session.commit()

    incoming_custs = [
        make_customer(1, name='Skip Customer', login='skip1', status_id=111349),
        make_customer(2, name='Sync Customer', login='sync2', status_id=100),
    ]
    incoming_leads = [
        make_lead(10, name='Skip Lead', login='sync2', status_id=143),
        make_lead(20, name='Sync Lead', login='sync2', status_id=200),
    ]

    with patch('main.amocrm_get', side_effect=[iter(incoming_custs), iter(incoming_leads)]):
        collect_leads_customers(is_full=False)

    # 1. Пропущенные по статусу не сохранены
    assert session.get(AmoCustomer, 1) is None
    assert session.get(AmoLead, 10) is None

    # 2. Обработанные сохранены
    assert session.get(AmoCustomer, 2) is not None
    assert session.get(AmoLead, 20) is not None

    # 3. Существовавший ранее покупатель 999 НЕ удален (очистка не запускалась)
    assert session.get(AmoCustomer, 999) is not None


def test_lead_action_single_call(session):
    """Тест одиночного вызова lead_action (не возвращает None, корректно работает)."""
    lead = make_lead(555, name='Standalone Lead', login='single_user')
    ac = lead_action(lead)

    assert ac is not None
    assert isinstance(ac, AbstractCustomer)
    db_lead = session.get(AmoLead, 555)
    assert db_lead is not None
    assert db_lead.abstract_customer_id == ac.id


def test_backward_compatibility_properties(session):
    """Проверка работы свойств amo_customers, amo_leads в формате JSON."""
    ac = AbstractCustomer()
    session.add(ac)
    session.flush()

    cust = AmoCustomer(
        id=701,
        abstract_customer_id=ac.id,
        login='prop_user',
        name='Prop Cust',
        billing_type='online',
        is_robot=False,
        is_nds=True,
        system='web',
        host='example.com',
        api_value={'custom_data': 123}
    )
    lead = AmoLead(
        id=702,
        abstract_customer_id=ac.id,
        login='prop_user',
        name='Prop Deal',
        api_value={'amount': 5000}
    )
    session.add_all([cust, lead])
    session.commit()

    db_ac = session.get(AbstractCustomer, ac.id)
    customers_json = db_ac.amo_customers
    leads_json = db_ac.amo_leads

    assert len(customers_json) == 1
    assert customers_json[0]['general']['id'] == 701
    assert customers_json[0]['general']['login'] == 'prop_user'
    assert customers_json[0]['general']['is_nds'] is True
    assert customers_json[0]['api_value']['custom_data'] == 123

    assert len(leads_json) == 1
    assert leads_json[0]['general']['id'] == 702
    assert leads_json[0]['general']['name'] == 'Prop Deal'
    assert leads_json[0]['api_value']['amount'] == 5000


def test_search_by_exact_login_and_name_and_relationship(session):
    """
    Проверка поддержки поисков другими частями системы:
    - точный логин
    - название
    - связь сделка-покупатель
    """
    ac = AbstractCustomer()
    session.add(ac)
    session.flush()

    cust = AmoCustomer(id=801, abstract_customer_id=ac.id, login='exact_login', name='Exact Name')
    lead = AmoLead(id=802, abstract_customer_id=ac.id, customer_id=cust.id, login='exact_login', name='Exact Deal')
    session.add_all([cust, lead])
    session.commit()

    # Поиск по логину
    found_cust = session.query(AmoCustomer).filter(AmoCustomer.login == 'exact_login').first()
    assert found_cust is not None
    assert found_cust.id == 801

    # Поиск по названию
    found_lead = session.query(AmoLead).filter(AmoLead.name == 'Exact Deal').first()
    assert found_lead is not None
    assert found_lead.id == 802

    # Связь сделка-покупатель
    assert found_lead.customer_id == 801
    assert found_lead.customer.name == 'Exact Name'
    assert len(found_cust.leads) == 1
    assert found_cust.leads[0].id == 802


def test_query_count_and_batch_efficiency(session):
    """
    Проверка пакетной эффективности:
    Для 2500 покупателей и 2500 сделок число запросов к базе должно быть O(число пачек),
    а не O(число сущностей). Старый код сделал бы >15 000 запросов.
    Наш код укладывается в < 50 запросов.
    """
    from sqlalchemy import event

    executed_queries = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        executed_queries.append(statement)

    engine = db.engine
    event.listen(engine, 'before_cursor_execute', before_cursor_execute)

    customers = [
        make_customer(i, name=f'Cust {i}', login=f'user_{i}')
        for i in range(1, 2501)
    ]
    leads = [
        make_lead(i, name=f'Lead {i}', login=f'user_{i}')
        for i in range(1, 2501)
    ]

    try:
        with patch('main.amocrm_get', side_effect=[iter(customers), iter(leads)]):
            collect_leads_customers(is_full=True)
    finally:
        event.remove(engine, 'before_cursor_execute', before_cursor_execute)

    query_count = len(executed_queries)
    assert query_count < 50, f"Ожидалось < 50 запросов, получено {query_count}"
    assert session.query(AmoCustomer).count() == 2500
    assert session.query(AmoLead).count() == 2500
