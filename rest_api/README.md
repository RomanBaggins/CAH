# REST API сервер для игры Cards Against Humanity

## Установка

Понадобятся Python 3.7 и pip. Рекомендуется все делать в отдельном venv'е.

Сначала надо установить зависимости.

```shell
pip install -r ./requirements.txt
```

Теперь проинициализируем базу данных.

```shell
python ./manage.py migrate
```

Готово! Можно запускать.

## Запуск

Прописываем

```shell
python ./manage.py 80
```

Теперь на localhost:80 поднялся сервер. Вместо 80 можно передать любой другой порт.

