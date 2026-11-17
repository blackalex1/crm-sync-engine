import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def bulk_upsert(session, model, records: List[Dict], update_cols: List[str], page_size: int = 2500):
    """
    Высокопроизводительный пакетный UPSERT (ON CONFLICT (id) DO UPDATE).
    Для PostgreSQL использует C-драйвер psycopg2.extras.execute_values (ускорение в десятки раз).
    Для SQLite (тесты) и fallback использует SQLAlchemy Core.
    """
    if not records:
        return

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind else 'postgresql'

    if dialect_name == 'postgresql':
        # Fast-path через psycopg2.extras.execute_values
        try:
            from psycopg2.extras import execute_values

            table_name = model.__tablename__
            keys = list(records[0].keys())
            cols_str = ', '.join(keys)
            update_set = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_cols])
            sql = f"""
            INSERT INTO {table_name} ({cols_str})
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET {update_set};
            """

            def prepare_val(v):
                if isinstance(v, (dict, list)):
                    return json.dumps(v)
                return v

            tuple_rows = [tuple(prepare_val(r.get(k)) for k in keys) for r in records]

            conn = session.connection()
            raw_conn = getattr(conn.connection, 'dbapi_connection', conn.connection)
            cursor = raw_conn.cursor()
            execute_values(cursor, sql, tuple_rows, page_size=page_size)
            cursor.close()
            return
        except Exception as e:
            logger.debug(f"Fast-path execute_values fallback to SQLAlchemy Core: {e}")

    # Fallback для SQLite и остальных диалектов
    if dialect_name == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert as insert_fn
    else:
        from sqlalchemy.dialects.postgresql import insert as insert_fn

    sub_size = 500
    for i in range(0, len(records), sub_size):
        sub_records = records[i:i + sub_size]
        stmt = insert_fn(model).values(sub_records)
        update_dict = {col: stmt.excluded[col] for col in update_cols}
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['id'],
            set_=update_dict
        )
        session.execute(upsert_stmt)
    session.flush()
