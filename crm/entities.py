TRANSACTIONS = "transactions"
TASKS = "tasks"
CUSTOMERS = "customers"
COMPANIES = "companies"
CONTACTS = "contacts"
CUSTOM_FIELDS = "custom_fields"
LEADS = "leads"
TAGS = "tags"
PIPELINES = "pipelines"
STATUSES = "statuses"
NOTES = "notes"
EVENTS = "events"


class BaseEntity:
    """Базовый класс для сущностей amoCRM."""
    schema = None
    entity_name = None
    url = None
    custom_fields_values = None
    PATCH_FIELDS = None

    def __str__(self):
        return f"<{type(self).__name__}: {getattr(self, 'name', None)}, {getattr(self, 'id', None)}>"

    def __repr__(self):
        return str(self)

    def get_field(self, field_name):
        return (self.custom_fields_values or {}).get(field_name, {}).get('value')

    def set_field(self, field_name, field_value, field_id=None):
        if self.custom_fields_values is None:
            self.custom_fields_values = {}
        custom_field = self.custom_fields_values.get(field_name)
        if custom_field is None:
            if field_id is None:
                raise KeyError(f"Not found custom field with key: {field_name}")
            self.custom_fields_values[field_name] = dict(id=field_id, value=field_value)
            return
        if custom_field.get('id'):
            custom_field['value'] = field_value
        elif field_id:
            custom_field['value'] = field_value
            custom_field['id'] = field_id
        else:
            raise ValueError(f"Custom field {field_name} without id")

    def get_url(self):
        return self.url

    def as_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    @classmethod
    def get_schema(cls, many=False):
        class _Schema:
            def load(self, data):
                return [cls(**item) for item in data]
        return _Schema()


class Customer(BaseEntity):
    """Класс покупателя amoCRM."""
    url = "api/v4/customers"
    entity_name = CUSTOMERS

    def __init__(self,
                 id=None,
                 name=None,
                 next_price=None,
                 next_date=None,
                 responsible_user_id=None,
                 status_id=None,
                 periodicity=None,
                 created_by=None,
                 updated_by=None,
                 created_at=None,
                 updated_at=None,
                 closest_task_at=None,
                 is_deleted=None,
                 ltv=None,
                 purchases_count=None,
                 average_check=None,
                 account_id=None,
                 custom_fields_values=None,
                 _embedded=None):
        self.id = id
        self.name = name
        self.next_price = next_price
        self.next_date = next_date
        self.responsible_user_id = responsible_user_id
        self.status_id = status_id
        self.periodicity = periodicity
        self.created_by = created_by
        self.updated_by = updated_by
        self.created_at = created_at
        self.updated_at = updated_at
        self.closest_task_at = closest_task_at
        self.is_deleted = is_deleted
        self.ltv = ltv
        self.purchases_count = purchases_count
        self.average_check = average_check
        self.account_id = account_id
        self.custom_fields_values = custom_fields_values
        self._embedded = _embedded

        self.companies = []
        self.contacts = []
        self._new_next_date = None
        if not _embedded:
            return
        if _embedded.get(COMPANIES):
            self.companies = _embedded.get(COMPANIES)
        if _embedded.get(CONTACTS):
            self.contacts = _embedded.get(CONTACTS)


class Lead(BaseEntity):
    """Класс сделки amoCRM."""
    url = "api/v4/leads"
    entity_name = LEADS
    PATCH_FIELDS = ("custom_fields_values", "id")

    def __init__(self,
                 name=None,
                 id=None,
                 price=None,
                 responsible_user_id=None,
                 group_id=None,
                 status_id=None,
                 pipeline_id=None,
                 source_id=None,
                 created_by=None,
                 updated_by=None,
                 created_at=None,
                 updated_at=None,
                 closest_task_at=None,
                 is_deleted=None,
                 score=None,
                 account_id=None,
                 custom_fields_values=None,
                 _embedded=None):
        self.id = id
        self.name = name
        self.price = price
        self.responsible_user_id = responsible_user_id
        self.group_id = group_id
        self.status_id = status_id
        self.pipeline_id = pipeline_id
        self.source_id = source_id
        self.created_by = created_by
        self.updated_by = updated_by
        self.created_at = created_at
        self.updated_at = updated_at
        self.closest_task_at = closest_task_at
        self.is_deleted = is_deleted
        self.score = score
        self.account_id = account_id
        self.custom_fields_values = custom_fields_values
        self._embedded = _embedded
        self.tags = []
        self.contacts = []
        self.companies = []
        if not _embedded:
            return
        if _embedded.get(CONTACTS):
            self.contacts = _embedded.get(CONTACTS)
        if _embedded.get(COMPANIES):
            self.companies = _embedded.get(COMPANIES)
