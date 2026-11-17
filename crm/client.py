import time
from typing import Type, Any, Iterator

import requests

from crm.entities import BaseEntity
from crm.exceptions import AmoCrmError, AmoCrmNoConten, AmoCrmRepeatError


def response_handler(response):
    if response.status_code == 204:
        raise AmoCrmNoConten(f"no content for {response.url}, method: {response.request.method}")
    elif response.status_code == 429:
        time.sleep(2)
        raise AmoCrmRepeatError()
    elif response.status_code != 200:
        json_data = {}
        try:
            json_data = response.json()
        except Exception:
            pass
        raise AmoCrmError(error_code=response.status_code, msg=json_data)
    return response.json()


def amocrm_get(obj_cls: Type[BaseEntity],
               page: int = None,
               limit: int = 250,
               _filter: dict = None,
               _with: str = None,
               query: Any = None,
               custom_filter: dict = None) -> Iterator[BaseEntity]:
    params = {}
    if page:
        params['page'] = page
    if limit:
        params['limit'] = limit
    if _filter:
        for key, value in _filter.items():
            filter_key = f'filter[{key}]'
            if isinstance(value, list):
                filter_key = f'{filter_key}[]'
            params[filter_key] = value
    if _with:
        if isinstance(_with, list):
            params['with'] = ",".join(_with)
        else:
            params['with'] = _with
    if query:
        params['query'] = query

    headers = {}
    base_url = ""
    url = f"{base_url}{obj_cls.url}"
    entity_name = obj_cls.entity_name
    schema = obj_cls.get_schema(many=True)

    while True:
        response = None
        json_data = None
        try:
            for try_attempt in range(4):
                try:
                    response = requests.get(url, params=params, headers=headers, timeout=120)
                    json_data = response_handler(response)
                    break
                except AmoCrmRepeatError as e:
                    if try_attempt >= 3:
                        raise e
                except AmoCrmNoConten:
                    raise
                except Exception as e:
                    raise AmoCrmError(f"[!] {response.status_code if response else '<No code!>'} |"
                                      f" Неожиданная AMOCRM ошибка {e} ") from e
        except AmoCrmNoConten:
            break

        if json_data is not None:
            counter = 0
            raw_entities = json_data.get('_embedded', {}).get(entity_name, [])
            for entity in schema.load(raw_entities):
                counter += 1
                skip_entity = False
                if custom_filter:
                    for key, value in custom_filter.items():
                        if entity.get_field(key) != value:
                            skip_entity = True
                            break
                if not skip_entity:
                    yield entity

            if page:
                break
            if counter < limit:
                break

            links = json_data.get('_links', {})
            next_link = links.get('next', {}).get('href')
            if not next_link:
                break

            time.sleep(1)
            url = next_link
            params = {}
