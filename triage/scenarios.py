"""Deterministic Persian intake: uncertainty leads to a question, not a guessed feature."""
FEATURES = ('aspect_sentiment_analysis', 'abstraction_analysis')
FEATURE_QUESTION = ('کدام قابلیت مشکل دارد؟\n1. aspect_sentiment_analysis — تحلیل احساسات جنبه‌ای\n'
                    '2. abstraction_analysis — تحلیل انتزاع / خلاصه‌سازی\nشماره یا نام قابلیت را بفرستید.')
SCENARIOS = {
    'aspect_sentiment_analysis': {
        '1': ('wrong_sentiment', 'احساس مثبت/منفی/خنثی اشتباه',
              [('aspect', 'کدام جنبه یا عبارت اشتباه تحلیل شده است؟'),
               ('expected', 'احساس مورد انتظار برای همان جنبه چیست و چرا؟')]),
        '2': ('missing_aspect', 'جنبه گم‌شده یا اضافی',
              [('aspect', 'کدام جنبه حذف شده یا نباید استخراج می‌شد؟'),
               ('expected', 'فهرست جنبه‌های مورد انتظار چیست؟')]),
        '3': ('empty_output', 'خروجی خالی', [('expected', 'برای این ورودی چه خروجی‌ای انتظار داشتید؟')]),
        '4': ('error', 'خطا یا کندی', [('error', 'متن خطا، کد پاسخ یا مدت انتظار چقدر بود؟')]),
    },
    'abstraction_analysis': {
        '1': ('incorrect_output', 'خروجی نادرست یا اطلاعات اضافه',
              [('mismatch', 'کدام عبارت خروجی با متن اصلی ناسازگار است؟'),
               ('expected', 'خروجی درست مورد انتظار چیست؟')]),
        '2': ('missing_content', 'حذف اطلاعات مهم',
              [('missing', 'کدام بخش مهم متن از خروجی حذف شده است؟'),
               ('expected', 'چه اطلاعاتی باید در خروجی باقی می‌ماند؟')]),
        '3': ('empty_output', 'خروجی خالی', [('expected', 'برای این ورودی چه خروجی‌ای انتظار داشتید؟')]),
        '4': ('error', 'خطا یا کندی', [('error', 'متن خطا، کد پاسخ یا مدت انتظار چقدر بود؟')]),
    },
}
COMMON = [('input', 'نمونه متن ورودی را بفرستید؛ اطلاعات حساس را حذف کنید.'),
          ('actual', 'خروجی واقعی یا رفتار مشاهده‌شده چه بود؟'),
          ('reproduction', 'مراحل بازتولید مشکل چیست؟'),
          ('environment', 'در کدام محیط/نسخه و حدود چه زمانی رخ داد؟'),
          ('request_id', 'شناسه درخواست یا لاگ متنی مرتبط دارید؟ اگر ندارید «نامشخص» بنویسید.')]


def normalize(text):
    return text.lower().replace('ي', 'ی').replace('ك', 'ک').replace('\u200c', ' ').strip()


def classify(text):
    text = normalize(text)
    matches = []
    if any(word in text for word in ('aspect_sentiment_analysis', 'احساس', 'sentiment')):
        matches.append(FEATURES[0])
    if any(word in text for word in ('abstraction_analysis', 'خلاصه', 'انتزاع', 'abstraction')):
        matches.append(FEATURES[1])
    return matches[0] if len(matches) == 1 else None


def scenario_question(feature):
    return 'نوع مشکل را انتخاب کنید:\n' + '\n'.join(f'{key}. {item[1]}' for key, item in SCENARIOS[feature].items())


def questions(data):
    scenario = next(item for item in SCENARIOS[data['feature']].values() if item[0] == data['scenario'])
    return COMMON[:2] + scenario[2] + COMMON[2:]


def next_question(data):
    if not data.get('feature'):
        return FEATURE_QUESTION
    if not data.get('scenario'):
        return scenario_question(data['feature'])
    for key, question in questions(data):
        if key not in data['answers']:
            return question
    return None
