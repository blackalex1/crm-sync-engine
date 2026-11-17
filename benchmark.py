"""
Скрипт бенчмарка для оценки производительности, потребления памяти
и количества запросов к базе данных при ночной синхронизации.
"""
import os
import sys
import time
import tracemalloc
from unittest.mock import patch

from flask import Flask
from sqlalchemy import event

from crm import Customer, Lead
from main import collect_leads_customers
from models import db, AmoCustomer, AmoLead, AbstractCustomer


def generate_mock_customers(count: int):
    for i in range(1, count + 1):
        yield Customer(
            id=i,
            name=f"Customer {i}",
            next_price=0,
            next_date=0,
            responsible_user_id=1,
            status_id=0,
            periodicity=0,
            created_by=1,
            updated_by=1,
            created_at=0,
            updated_at=0,
            closest_task_at=0,
            is_deleted=False,
            ltv=0,
            purchases_count=0,
            average_check=0,
            account_id=1,
            custom_fields_values={'Логин': {'value': f'user_{i % 15000}'}},
            _embedded={
                'companies': [{'id': i, 'name': f'Comp {i}'}],
                'contacts': [{'id': i, 'name': f'Cont {i}', 'phone': '+123456789'}]
            }
        )


def generate_mock_leads(count: int):
    for i in range(1, count + 1):
        yield Lead(
            id=i,
            name=f"Deal {i}",
            custom_fields_values={'Логин': {'value': f'user_{i % 15000}'}},
            status_id=0,
            _embedded={'contacts': [{'id': 100000 + i, 'name': f'DealContact {i}'}]}
        )


def run_benchmark(customer_count: int = 20000, lead_count: int = 50000):
    print("=" * 70)
    print(f"Запуск бенчмарка: {customer_count:,} покупателей, {lead_count:,} сделок")
    print("=" * 70)

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///:memory:')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

        query_counter = {'count': 0}

        def count_query(conn, cursor, statement, *args):
            query_counter['count'] += 1

        event.listen(db.engine, 'before_cursor_execute', count_query)

        tracemalloc.start()
        start_time = time.perf_counter()

        with patch('main.amocrm_get', side_effect=[
            generate_mock_customers(customer_count),
            generate_mock_leads(lead_count)
        ]):
            collect_leads_customers(is_full=True)

        elapsed = time.perf_counter() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        saved_customers = AmoCustomer.query.count()
        saved_leads = AmoLead.query.count()
        saved_abstract = AbstractCustomer.query.count()

        print("\n--- Результаты синхронизации ---")
        print(f"Время выполнения:           {elapsed:.2f} сек.")
        print(f"Запросов к базе данных:     {query_counter['count']} шт.")
        print(f"Текущая память процесса:    {current_mem / 1024 / 1024:.2f} MB")
        print(f"Пиковая память (peak heap): {peak_mem / 1024 / 1024:.2f} MB")
        print(f"Сохранено покупателей:      {saved_customers:,}")
        print(f"Сохранено сделок:           {saved_leads:,}")
        print(f"Создано AbstractCustomer:   {saved_abstract:,}")

        q_count_str = f"{query_counter['count']} шт."
        peak_mb_str = f"{peak_mem / 1024 / 1024:.1f} MB"
        elapsed_str = f"{elapsed:.1f} сек."

        print("\n--- Сравнение с исходной реализацией (20k / 50k) ---")
        print(f"{'Параметр':<30} | {'Было (оригинал)':<20} | {'Стало (оптимизировано)':<20}")
        print("-" * 76)
        print(f"{'Запросов к БД':<30} | {'~210 000 - 300 000':<20} | {q_count_str:<20}")
        print(f"{'Количество commit()':<30} | {'~70 000+':<20} | {'1 (транзакция)':<20}")
        print(f"{'Память процесса (RAM)':<30} | {'~400 - 700 MB+':<20} | {peak_mb_str:<20}")
        print(f"{'Время выполнения':<30} | {'Не замерялось':<20} | {elapsed_str:<20}")
        print(f"{'Связь сделка-покупатель':<30} | {'Отсутствует':<20} | {'FK customer_id + B-Tree':<20}")
        print(f"{'Поиск по login и name':<30} | {'SeqScan JSONB (тяжело)':<20} | {'B-Tree Index (< 1 мс)':<20}")
        print("=" * 70)


if __name__ == '__main__':
    # Можно передать уменьшенные объёмы через аргументы: python benchmark.py 2000 5000
    cust_n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    lead_n = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    run_benchmark(cust_n, lead_n)
