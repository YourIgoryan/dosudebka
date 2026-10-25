# Досудебка: сайт для самозанятых

Запуск (нужен только Python 3.8+):

    python app.py          # http://127.0.0.1:8000
    PORT=9000 python app.py

Структура:

    app.py                 сервер и маршруты
    templates/             HTML-страницы ({{ключ}} подставляется кодом)
    static/style.css       стили
    content/posts/*.html   статьи блога (шапка: title, date, sort, lead; затем ---)
    content/templates.json каталог шаблонов документов
    downloads/*.txt        файлы шаблонов для скачивания
    data/bookings.csv      заявки с формы (создаётся сам)

Новая статья: добавьте файл в content/posts/. Новый шаблон: положите .txt в downloads/
и добавьте запись в content/templates.json. Перезапуск не нужен.
