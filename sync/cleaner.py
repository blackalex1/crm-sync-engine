import logging
from sqlalchemy import delete, or_, and_, func, select

from models import (
    AbstractCustomer,
    AmoCustomer,
    AmoLead,
    AmoCompany,
    AmoContact
)

logger = logging.getLogger(__name__)


def cleanup_unseen_entities(session, sync_run_id: str):
    """
    Атомарная очистка сущностей в БД после успешного полного прохода:
    - Удаляет сущности, которых не было в текущей выгрузке (sync_run_id != текущему).
    - Удаляет сущности, содержащие в имени слово «удалить» (регистронезависимо).
    - Удаляет агрегаты AbstractCustomer, у которых не осталось ни покупателей, ни сделок.
    """
    logger.info("Запуск очистки устаревших и помеченных сущностей...")

    # 1. Покупатели
    session.execute(
        delete(AmoCustomer).where(
            or_(
                AmoCustomer.sync_run_id != sync_run_id,
                AmoCustomer.sync_run_id.is_(None),
                func.lower(AmoCustomer.name).like('%удалить%'),
                AmoCustomer.name.like('%УДАЛИТЬ%'),
                AmoCustomer.name.like('%Удалить%')
            )
        )
    )

    # 2. Сделки
    session.execute(
        delete(AmoLead).where(
            or_(
                AmoLead.sync_run_id != sync_run_id,
                AmoLead.sync_run_id.is_(None),
                func.lower(AmoLead.name).like('%удалить%'),
                AmoLead.name.like('%УДАЛИТЬ%'),
                AmoLead.name.like('%Удалить%')
            )
        )
    )

    # 3. Компании
    session.execute(
        delete(AmoCompany).where(
            or_(
                AmoCompany.sync_run_id != sync_run_id,
                AmoCompany.sync_run_id.is_(None),
                func.lower(AmoCompany.name).like('%удалить%'),
                AmoCompany.name.like('%УДАЛИТЬ%'),
                AmoCompany.name.like('%Удалить%')
            )
        )
    )

    # 4. Контакты
    session.execute(
        delete(AmoContact).where(
            or_(
                AmoContact.sync_run_id != sync_run_id,
                AmoContact.sync_run_id.is_(None),
                func.lower(AmoContact.name).like('%удалить%'),
                AmoContact.name.like('%УДАЛИТЬ%'),
                AmoContact.name.like('%Удалить%')
            )
        )
    )

    # 5. Пустые AbstractCustomer
    has_customers = select(1).where(AmoCustomer.abstract_customer_id == AbstractCustomer.id).exists()
    has_leads = select(1).where(AmoLead.abstract_customer_id == AbstractCustomer.id).exists()
    session.execute(
        delete(AbstractCustomer).where(
            and_(~has_customers, ~has_leads)
        )
    )

    session.commit()
    logger.info("Очистка успешно завершена.")
