"""
agent2/generator/template_generator.py
Генерация постов через шаблоны — без LLM, мгновенно.
"""
import random

TEMPLATES = {
    "кейс": [
"""{hook}

Год назад я {struggle}.

Что изменилось:
→ {action_1}
→ {action_2}
→ {action_3}

Результат: {result}

Главный урок: {lesson}

{hashtags}""",
"""{hook}

Конкретные цифры:
До: {before}
После: {after}

Что я сделал:
1. {action_1}
2. {action_2}
3. {action_3}

{cta}

{hashtags}"""],
    "совет": [
"""{hook}

Вот что реально меняет подход к {topic}:

{tips_list}

Сохраните — пригодится.

{hashtags}""",
"""Один совет о {topic}:

{main_tip}

Почему это работает: {reason}

Попробуйте сегодня: {action}

{hashtags}"""],
    "история": [
"""{hook}

{story_setup}

В тот момент я понял: {insight}

Теперь я {current_state}.

Если вы тоже {reader_situation} — начните с этого:
{first_step}

{hashtags}"""],
    "список": [
"""{hook}

{list_items}

Какой пункт откликается?

{hashtags}"""],
    "мнение": [
"""Непопулярное мнение о {topic}:

{opinion}

Почему я так думаю:
— {reason_1}
— {reason_2}

Согласны? Пишите в комментарии.

{hashtags}"""],
    "короткий совет": ["""{hook}\n\n{main_tip}\n\n{hashtags}"""],
    "разбор": [
"""Разбираю: {topic}

— {point_1}
— {point_2}
— {point_3}

Итог: {conclusion}

{hashtags}"""],
    "вопрос аудитории": [
"""{question}

Мой ответ: {answer}

А вы как считаете?

{hashtags}"""],
    "история успеха": [
"""{hook}

{story_setup}

Три вещи которые помогли:
✦ {action_1}
✦ {action_2}
✦ {action_3}

{cta}

{hashtags}"""],
    "карусель": [
"""Слайд 1: {hook}
---
Слайд 2: {point_1}
---
Слайд 3: {point_2}
---
Слайд 4: {point_3}
---
Слайд 5: {cta}

{hashtags}"""],
}

HOOKS = {
    "salary":      ["Я вырос по зарплате на 40% за 8 месяцев. Без смены работы.","Большинство людей недооценивают себя на рынке труда.","Честный разговор о деньгах — которого все избегают."],
    "linkedin":    ["Ваш LinkedIn профиль работает против вас — вот почему.","LinkedIn изменил мою карьеру. Вот что я делал каждую неделю.","Один пост в LinkedIn принёс мне 3 оффера за месяц."],
    "brand":       ["Личный бренд — это не про эго. Это про деньги.","Почему 90% специалистов невидимы на рынке труда.","Я начал вести соцсети полгода назад. Вот что изменилось."],
    "skills":      ["Навыки за которые платят больше всего в 2025 году.","Работодатели не ищут дипломы. Они ищут вот это.","Один навык удвоил мою ценность на рынке."],
    "career":      ["Карьера — это не лестница. Это игра с правилами.","Что отличает тех кто растёт быстро от тех кто стоит на месте.","Жёсткая правда о карьерном росте которую никто не говорит вслух."],
    "default":     ["Делюсь тем что реально работает в моей практике.","Честный опыт — без приукрашивания.","То что я хотел бы знать 3 года назад."],
}

HASHTAGS = {
    "IT":        {"LinkedIn":["#developer","#techcareer","#softwareengineering","#coding","#personalbrand"],"Telegram":["#it","#карьера","#разработка"],"Instagram":["#developer","#techlife","#coding","#softwaredeveloper","#career","#tech2025","#personalbrand","#linkedin","#remotework","#itcareer"]},
    "маркетинг": {"LinkedIn":["#marketing","#digitalmarketing","#contentmarketing","#smm","#personalbrand"],"Telegram":["#маркетинг","#smm","#контент"],"Instagram":["#marketing","#smm","#contentcreator","#digitalmarketing","#marketingtips","#socialmedia","#brand","#маркетинг"]},
    "карьера":   {"LinkedIn":["#карьера","#personalbrand","#linkedin","#профразвитие","#зарплата"],"Telegram":["#карьера","#рост","#работа"],"Instagram":["#карьера","#работа","#успех","#мотивация","#профессионализм","#карьерныйрост","#linkedin"]},
    "финансы":   {"LinkedIn":["#finance","#personalfinance","#investing","#salary","#financialfreedom"],"Telegram":["#финансы","#деньги","#инвестиции"],"Instagram":["#финансы","#деньги","#инвестиции","#пассивныйдоход","#финансоваясвобода","#богатство"]},
    "общее":     {"LinkedIn":["#personalbrand","#productivity","#growth","#leadership","#career"],"Telegram":["#продуктивность","#развитие","#карьера"],"Instagram":["#мотивация","#успех","#развитие","#продуктивность","#лайфстайл","#карьера"]},
}

def _get_hashtags(niche, platform, max_tags=5):
    tags = HASHTAGS.get(niche, HASHTAGS["общее"]).get(platform, [])
    return " ".join(tags[:max_tags])

def generate_from_template(slot, profile):
    post_format = slot.get("format","совет")
    templates   = TEMPLATES.get(post_format, TEMPLATES["совет"])
    template    = random.choice(templates)

    trend    = slot.get("trend", {})
    keywords = trend.get("keywords", [])
    niche    = profile.get("niche","общее")
    platform = slot.get("platform","LinkedIn")
    goal     = profile.get("goal","карьерный рост")
    prof     = profile.get("profession","специалист")
    topic    = keywords[0] if keywords else goal

    kw_str = " ".join(keywords).lower()
    trend_type = "default"
    for t in ["salary","linkedin","brand","skills","career"]:
        if t in kw_str: trend_type = t; break

    limits = {"LinkedIn":5,"Telegram":3,"Instagram":15}
    hashtags = _get_hashtags(niche, platform, limits.get(platform,5))
    hook = random.choice(HOOKS.get(trend_type, HOOKS["default"]))

    subs = {
        "{hook}":hook,"{topic}":topic,"{hashtags}":hashtags,
        "{profession}":prof,"{goal}":goal,
        "{struggle}":f"не понимал как использовать {topic} для {goal}",
        "{action_1}":f"начал системно работать над {keywords[0] if keywords else topic}",
        "{action_2}":f"изучил как {keywords[1] if len(keywords)>1 else 'это'} влияет на результат",
        "{action_3}":f"применил это в своей практике как {prof}",
        "{result}":f"достиг прогресса в направлении «{goal}»",
        "{lesson}":"Системность важнее интенсивности",
        "{before}":f"работал без стратегии в области {topic}",
        "{after}":"чёткая система + измеримые результаты",
        "{cta}":"Сохраните этот пост и вернитесь к нему через месяц.",
        "{tip_count}":str(random.randint(3,7)),
        "{tips_list}":"\n".join([f"→ {kw.capitalize()}" for kw in keywords[:4]]) or "→ Фокус\n→ Цели\n→ Регулярность",
        "{main_tip}":f"Сфокусируйтесь на {topic} — это даёт максимальный результат в {goal}.",
        "{reason}":f"{topic} напрямую влияет на {goal}.",
        "{action}":f"Выделите 20 минут на анализ своего подхода к {topic}.",
        "{story_setup}":f"Я работал как {prof} и столкнулся с типичной проблемой: {topic} казался недостижимым.",
        "{insight}":f"важно не количество усилий, а правильный вектор в {topic}",
        "{current_state}":f"уверенно двигаюсь к цели «{goal}»",
        "{reader_situation}":f"работаете над {topic}",
        "{first_step}":f"Начните с малого: один шаг в сторону {topic} сегодня.",
        "{list_items}":"\n".join([f"{i+1}. {kw.capitalize()}" for i,kw in enumerate(keywords[:5])]) or "1. Фокус\n2. Системность\n3. Практика",
        "{opinion}":f"большинство специалистов недооценивают {topic} в контексте {goal}",
        "{reason_1}":f"Данные показывают: {topic} — ключевой фактор",
        "{reason_2}":f"Мой опыт как {prof} это подтверждает",
        "{point_1}":f"Что такое {keywords[0] if keywords else topic} и почему это важно",
        "{point_2}":f"Как применить в контексте {goal}",
        "{point_3}":"Частые ошибки и как их избежать",
        "{conclusion}":f"Инвестиции в {topic} окупаются быстро при системном подходе.",
        "{question}":f"Как вы подходите к {topic} в своей карьере?",
        "{answer}":f"Я как {prof}: {keywords[0] if keywords else 'системно и регулярно'}.",
    }
    result = template
    for k, v in subs.items(): result = result.replace(k, str(v))
    return result.strip()
