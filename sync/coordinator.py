import gc
import logging
import uuid
from typing import Iterator, Dict, Optional, Tuple

from sqlalchemy import text

from crm.client import amocrm_get
from crm.entities import Customer, Lead, COMPANIES, CONTACTS
from models import db
from sync.chunker import chunked
from sync.customers import sync_customers_batch
from sync.leads import sync_leads_batch
from sync.cleaner import cleanup_unseen_entities

logger = logging.getLogger(__name__)

BATCH_SIZE = 2500


def collect_leads_customers(is_full: bool = True):
    """
    Высокопроизводительная ночная пакетная синхронизация покупателей и сделок из CRM в Postgres.
    Точка входа — collect_leads_customers(is_full=True).
    Рассчитана на нагрузку 20 тыс. покупателей и 50 тыс. сделок.
    
    Бизнес-правила:
    - Покупатель без логина пропускается.
    - Покупатель ищется по id CRM, иначе по логину среди уже сохранённых сделок.
      Если по логину нашлось больше одной записи, совпадение не используется.
    - Сделка ищется по id сделки в CRM, иначе по логину среди покупателей.
      Если это две разные записи, они сливаются в ту, что нашли по сделке; вторая удаляется.
      Если не нашлось ничего, создаётся новая запись.
    - После успешного полного прохода удаляются покупатели и вложенные сущности,
      которых не было в этой выгрузке, в том числе с «удалить» в имени.
    - Если сбор прервался, удаление не запускается.
    """
    session = db.session
    sync_run_id = uuid.uuid4().hex
    logger.info(f"Начало синхронизации: {sync_run_id=}, {is_full=}")

    # Оптимизация параметров транзакции в PostgreSQL
    bind = session.get_bind()
    if bind and bind.dialect.name == 'postgresql':
        try:
            session.execute(text("SET LOCAL synchronous_commit = off;"))
            session.execute(text("SET LOCAL work_mem = '64MB';"))
        except Exception as e:
            logger.debug(f"Session tuning ignored: {e}")

    # Кэш логинов покупателей между шагом 1 и шагом 2 (устраняет SELECT к БД)
    customer_login_cache: Dict[str, Optional[Tuple[int, int]]] = {}

    gc.disable()
    try:
        # Поддержка патчинга через main.amocrm_get для тестов и обратной совместимости
        import sys
        main_mod = sys.modules.get('main')
        fetcher = getattr(main_mod, 'amocrm_get', amocrm_get)

        # =====================================================================
        # ЭТАП 1: Обработка покупателей (пакетный потоковый режим)
        # =====================================================================
        customers_iter: Iterator[Customer] = fetcher(Customer, _with=f"{COMPANIES},{CONTACTS}")
        for batch in chunked(customers_iter, BATCH_SIZE):
            sync_customers_batch(
                session, batch, sync_run_id, is_full=is_full,
                customer_login_cache=customer_login_cache
            )
        logger.info("Покупатели успешно обработаны.")

        # =====================================================================
        # ЭТАП 2: Обработка сделок (пакетный потоковый режим)
        # =====================================================================
        leads_iter: Iterator[Lead] = fetcher(Lead, _with=f"{CONTACTS}")
        for batch in chunked(leads_iter, BATCH_SIZE):
            sync_leads_batch(
                session, batch, sync_run_id, is_full=is_full,
                customer_login_cache=customer_login_cache
            )
        logger.info("Сделки успешно обработаны.")

    except Exception as e:
        session.rollback()
        logger.exception(f"Сбор данных прервался из-за ошибки: {e}. Удаление отменено.")
        raise
    finally:
        gc.enable()
        gc.collect()

    # =========================================================================
    # ЭТАП 3: Очистка (только при полном успешном проходе)
    # =========================================================================
    if not is_full:
        session.commit()
        logger.info("Неполный прогон завершён успешно (очистка не требуется).")
        return

    cleanup_unseen_entities(session, sync_run_id)
