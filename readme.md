# Floreal Paris: Настройка
> **ВАЖНО!** У вас должен быть установлен PostgreSQL 
1. Установить зависимости (желательно в виртуальную среду)
```bash
pip install -r requirements.txt 
```
2. В файле `manager_of_floreal_paris/settings.py` вписать свои значения в `DATABASES` для полей `USER`; `PASSWORD`;
`NAME`
3. Мигрировать.
```bash
py manage.py migrate
```