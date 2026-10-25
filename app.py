#!/usr/bin/env python3
"""Досудебка: сайт для самозанятых. Только стандартная библиотека.
Запуск: python app.py  ->  http://127.0.0.1:8000"""
import csv, html, json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 8000))
BOOKINGS = os.path.join(ROOT, "data", "bookings.csv")
e = html.escape
NAV = [("/", "Главная"), ("/consult", "Консультации"), ("/templates", "Шаблоны"),
       ("/blog", "Блог"), ("/diagnostic", "Диагностика"), ("/book", "Записаться")]
TOPICS = ["Диагностика", "Претензия", "Претензия и суд", "Разбор с юристом", "Договор для моей работы", "Другое"]
LOCK = threading.Lock()
EVID = {"chat": 2, "handed": 2, "act": 1, "check": 1, "partial": 1, "confess": 2}

def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()

def render(tpl, /, **ctx):  # подстановка {{ключ}}; content всегда последним
    s = read("templates", tpl + ".html")
    for k, v in ctx.items():
        s = s.replace("{{%s}}" % k, v)
    return s

def page(title, content, path="/"):
    nav = "".join('<a href="%s"%s>%s</a>' % (h, ' aria-current="page"' if h == path else "", t) for h, t in NAV)
    return render("base", title=e(title), nav=nav, content=content)

def posts():
    out, d = [], os.path.join(ROOT, "content", "posts")
    for fn in os.listdir(d):
        if fn.endswith(".html"):
            head, body = read("content", "posts", fn).split("\n---\n", 1)
            m = dict(l.split(": ", 1) for l in head.splitlines())
            m.update(slug=fn[:-5], body=body)
            out.append(m)
    return sorted(out, key=lambda m: m["sort"], reverse=True)

def card(m):
    return '<a class="item" href="/blog/%s"><h3>%s</h3><p class="meta">%s</p><p>%s</p></a>' % (m["slug"], e(m["title"]), e(m["date"]), e(m["lead"]))

def p_home():
    return page("Главная", render("home", latest="".join(card(m) for m in posts()[:2])), "/")

def p_blog():
    return page("Блог", render("blog", cards="".join(card(m) for m in posts())), "/blog")

def p_post(slug):
    m = next((x for x in posts() if x["slug"] == slug), None)
    if not m:
        return None
    return page(m["title"], render("post", date=e(m["date"]), title=e(m["title"]), lead=e(m["lead"]), body=m["body"]), "/blog")

def p_catalog():
    items = json.loads(read("content", "templates.json"))
    cards = "".join('<div class="box"><h3>%s</h3><p>%s</p><a class="btn alt" href="/files/%s.txt" download>Скачать</a></div>'
                    % (e(i["title"]), e(i["desc"]), i["slug"]) for i in items)
    return page("Шаблоны", render("catalog", cards=cards), "/templates")

def p_book(err="", v=None, sent=False):
    v = v or {}
    if sent:
        return page("Запись", "<h1>Запись на консультацию</h1><div class='ok'><b>Заявка принята.</b> Мы свяжемся с вами в течение рабочего дня.</div>", "/book")
    opts = "".join("<option%s>%s</option>" % (" selected" if v.get("topic") == t else "", e(t)) for t in TOPICS)
    msg = '<div class="err" role="alert">%s</div>' % e(err) if err else ""
    return page("Запись", render("book", message=msg, name=e(v.get("name", "")), contact=e(v.get("contact", "")), options=opts, msg=e(v.get("msg", ""))), "/book")

def diagnose(f):
    one = lambda k: f.get(k, [""])[0]
    score = {"written": 3, "chat": 2}.get(one("contract"), 0) + sum(EVID.get(k, 0) for k in f.get("ev", []))
    level = "высокие" if score >= 7 else "средние" if score >= 4 else "низкие"
    notes = []
    if one("age") == "old":
        notes.append("Срок исковой давности — три года. Проверьте дату, возможно, он уже истёк или подходит к концу.")
    if one("amount") == "big":
        notes.append("Сумма выше 500 000 ₽: судебный приказ мирового судьи не подходит, потребуется иск. Лучше обсудить дело с юристом.")
    else:
        notes.append("Сумма в пределах 500 000 ₽: после претензии можно просить судебный приказ.")
    if one("who") == "org":
        notes.append("Если вы ИП, а заказчик организация или ИП, спор пойдёт в арбитраж, а претензионный срок там 30 дней.")
    if one("state") == "promise":
        notes.append("Попросите заказчика написать срок оплаты в мессенджере: признание долга пригодится в суде.")
    if one("state") == "silent":
        notes.append("Отправьте претензию письмом с описью вложения и продублируйте в мессенджере.")
    if one("contract") == "oral" and score < 4:
        notes.append("Без договора и переписки собрать доказательства сложнее. Вспомните чеки, переводы и свидетелей.")
    lst = "".join("<li>%s</li>" % e(n) for n in notes)
    return ('<div class="box result"><div class="lvl">Шансы взыскания: %s</div><p>Оценка по доказательствам: %d из 12.</p><ul>%s</ul>'
            '<h3>Что сделать за 48 часов</h3><ul><li>Сохраните переписку со скриншотами с датой и номером.</li>'
            '<li>Найдите чеки, акты и частичные оплаты.</li><li>Не угрожайте заказчику, спокойно уточните сумму долга.</li></ul>'
            '<a class="btn" href="/book">Записаться на консультацию</a></div>') % (level, score, lst)

def p_diag(result=""):
    return page("Диагностика", render("diag", result=result), "/diagnostic")

ROUTES = {"/": p_home, "/consult": lambda: page("Консультации", read("templates", "consult.html"), "/consult"),
          "/templates": p_catalog, "/blog": p_blog, "/book": p_book, "/diagnostic": p_diag}

class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, ctype="text/html; charset=utf-8", headers=()):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, to):
        self.send_response(303); self.send_header("Location", to); self.send_header("Content-Length", "0"); self.end_headers()

    def not_found(self):
        self.reply(404, page("Не найдено", read("templates", "404.html")))

    def do_GET(self):
        u = urlparse(self.path)
        p = u.path.rstrip("/") or "/"
        if p == "/book" and "sent" in parse_qs(u.query):
            return self.reply(200, p_book(sent=True))
        if p in ROUTES:
            return self.reply(200, ROUTES[p]())
        if p.startswith("/blog/"):
            h = p_post(p[6:])
            return self.reply(200, h) if h else self.not_found()
        if p.startswith("/static/"):
            f = os.path.join(ROOT, "static", os.path.basename(p))
            if os.path.isfile(f):
                with open(f, "rb") as fh:
                    return self.reply(200, fh.read(), "text/css; charset=utf-8", [("Cache-Control", "max-age=3600")])
        if p.startswith("/files/") and p.endswith(".txt"):
            slug = os.path.basename(p)[:-4]
            if slug in {i["slug"] for i in json.loads(read("content", "templates.json"))}:
                return self.reply(200, read("downloads", slug + ".txt"), "text/plain; charset=utf-8",
                                  [("Content-Disposition", "attachment; filename=%s.txt" % slug)])
        self.not_found()

    def do_POST(self):
        p = urlparse(self.path).path.rstrip("/")
        n = min(int(self.headers.get("Content-Length") or 0), 10000)
        raw = parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        if p == "/diagnostic":
            return self.reply(200, p_diag(diagnose(raw)))
        if p != "/book":
            return self.not_found()
        f = {k: v[0].strip() for k, v in raw.items()}
        if f.get("website"):
            return self.redirect("/book?sent=1")
        if not f.get("name") or not f.get("contact"):
            return self.reply(400, p_book("Укажите имя и способ связи.", f))
        if f.get("consent") != "1":
            return self.reply(400, p_book("Нужно согласие на обработку данных.", f))
        row = [time.strftime("%Y-%m-%d %H:%M"), f["name"][:80], f["contact"][:80], f.get("topic", "")[:60], f.get("msg", "")[:1500]]
        row = [("'" + c if c.startswith(("=", "+", "-", "@")) else c) for c in row]  # защита от формул при открытии в Excel
        with LOCK:  # один писатель за раз
            os.makedirs(os.path.dirname(BOOKINGS), exist_ok=True)
            new = not os.path.exists(BOOKINGS)
            with open(BOOKINGS, "a", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh)
                if new:
                    w.writerow(["время", "имя", "контакт", "тема", "сообщение"])
                w.writerow(row)
        self.redirect("/book?sent=1")

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    print("Сайт: http://127.0.0.1:%d  (остановка: Ctrl+C)" % PORT)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
