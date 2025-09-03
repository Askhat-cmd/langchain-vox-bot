# тестовый скрипт для проверки агента на наличие ключевых слов в ответе на вопросы,
# проверяет на сколько агент понимает контекст и отвечает на вопросы по нему.
# запускается из корневой папки проекта: python test_agent.py

'''
Этот скрипт — ваш личный "контролёр качества". Его нужно запускать **каждый раз** после того,
как вы:

1.  **Обновляете базу знаний** (`knowledge_base.md`).
2.  **Изменяете промпты** (через админ-панель или напрямую в `prompts.json`).

Это позволит вам мгновенно убедиться, что после внесенных изменений бот не "разучился"
отвечать на самые важные и частые вопросы. Если какой-то тест провалится, вы сразу поймете,
что что-то пошло не так, и сможете вовремя это исправить.
Это превращает рутинную ручную проверку в быстрый автоматизированный процесс.
'''

import asyncio
import os
import sys
import uuid
import logging
from dotenv import load_dotenv

# Добавляем корневую директорию в путь, чтобы можно было импортировать Agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Настраиваем логирование, чтобы видеть меньше спама от библиотек
logging.basicConfig(level=logging.WARNING)
# Устанавливаем уровень INFO только для нашего кастомного логгера, если нужно
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    from Agent import Agent
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что вы запускаете скрипт из корневой папки проекта или что путь к Agent.py корректен.")
    sys.exit(1)

# --- ТЕСТОВЫЕ СЛУЧАИ (ОДИНОЧНЫЕ) ---
# Проверяют базовые знания бота по конкретным темам.
SINGLE_CASES = [
    {
        "name": "Проверка категорий товаров",
        "question": "Какие категории мебели представлены в вашем магазине?",
        "expected_keywords": ["диваны", "кресла", "пуфы", "банкетки"]
    },
    {
        "name": "Проверка видов диванов",
        "question": "Какие виды диванов у вас есть?",
        "expected_keywords": ["прямые", "угловые", "диваны-кровати"]
    },
    {
        "name": "Проверка описания угловых диванов",
        "question": "Расскажите про угловые диваны",
        "expected_keywords": ["просторные", "больших помещений", "конфигурации"]
    },
    {
        "name": "Проверка деталей о диване «Классик»",
        "question": "Что можно сказать про конструкцию и функции дивана «Классик»?",
        "expected_keywords": ["сосны", "боннель", "книжка", "200х140", "ящик", "45000"]
    },
    {
        "name": "Проверка деталей о диване «Модерн Плюс»",
        "question": "Расскажите про диван «Модерн Плюс» и его особенности",
        "expected_keywords": ["еврокнижка", "тефлоновой", "подушки-валики"]
    },
    {
        "name": "Проверка деталей о диване «Престиж Люкс»",
        "question": "Чем особенен диван «Престиж Люкс»?",
        "expected_keywords": ["pocket spring", "электрический механизм", "натуральной кожи", "премиум-класса"]
    },
    {
        "name": "Проверка наличия компактных диванов",
        "question": "Посоветуйте небольшой угловой диван для маленькой комнаты",
        "expected_keywords": ["компакт", "выкатной", "180х120", "место хранения"]
    },
    {
        "name": "Проверка цены дивана «Престиж Люкс»",
        "question": "Сколько стоит диван «Престиж Люкс»?",
        "expected_keywords": ["125000", "рублей"]
    },
    {
        "name": "Проверка цветов дивана «Эконом Стандарт»",
        "question": "В каких цветах выпускается модель «Эконом Стандарт»?",
        "expected_keywords": ["серый", "коричневый", "синий", "серо-голубой"]
    },
    {
        "name": "Проверка механизма трансформации",
        "question": "Какой механизм трансформации у дивана «Ночной Комфорт»?",
        "expected_keywords": ["дельфин"]
    },
    {
        "name": "Проверка условий доставки и сборки",
        "question": "Расскажите про условия доставки и сборки.",
        "expected_keywords": ["30000", "бесплатн", "подъем на этаж", "сборка", "2 года"]
    },
    {
        "name": "Проверка информации о гарантии",
        "question": "Какую гарантию вы даёте на мебель?",
        "expected_keywords": ["2 до 5 лет", "2 года", "5 лет"]
    },
    {
        "name": "Проверка способов оплаты и рассрочки",
        "question": "Какие способы оплаты вы принимаете?",
        "expected_keywords": ["наличные", "банковск", "рассрочка", "24", "без процентов"]
    },
    {
        "name": "Проверка возможности индивидуального заказа мебели",
        "question": "Как осуществляется индивидуальный заказ мебели?",
        "expected_keywords": ["3 недели", "15", "30%"]
    },
    {
        "name": "Проверка адреса магазина",
        "question": "Какой у вас адрес?",
        "expected_keywords": ["ул. мебельная, 25"]
    },
    {
        "name": "Проверка телефона магазина",
        "question": "Скажите номер телефона магазина",
        "expected_keywords": ["495", "123-45-67"]
    },
    {
        "name": "Проверка времени работы",
        "question": "Подскажите режим работы магазина",
        "expected_keywords": ["10:00", "21:00"]
    }
]

# --- СЦЕНАРНЫЕ ТЕСТЫ ---
# Проверяют способность бота поддерживать контекст диалога.
SCENARIO_CASES = [
    {
        "name": "Сценарий: Подбор дивана для ежедневного сна в семье",
        "steps": [
            {
                "question": "Нужен диван-кровать для ежедневного сна.",
                "expected_keywords": ["диваны-кровати", "ежедневного сна", "ночной комфорт"]
            },
            {
                "question": "У нас семья с ребёнком, хотелось бы учесть это.",
                "expected_keywords": ["семейное гнездо", "двухуровневая", "250 кг"]
            }
        ]
    },
    {
        "name": "Сценарий: Подбор компактного углового дивана",
        "steps": [
            {
                "question": "Мне нужен небольшой угловой диван в маленькую комнату.",
                "expected_keywords": ["компакт", "местом хранения"]
            },
            {
                "question": "А его можно использовать как кровать?",
                "expected_keywords": ["выкатной", "180х120"]
            },
            {
                "question": "И сколько он стоит?",
                "expected_keywords": ["54000", "рублей"]
            }
        ]
    },
    {
        "name": "Сценарий: Выбор классического дивана и уточнение функций",
        "steps": [
            {
                "question": "Посоветуйте диван в классическом стиле.",
                "expected_keywords": ["классик", "велюра", "экокожи"]
            },
            {
                "question": "Он раскладывается в кровать?",
                "expected_keywords": ["книжка", "200х140", "ящик"]
            },
            {
                "question": "Сколько он стоит?",
                "expected_keywords": ["45000", "рублей"]
            }
        ]
    },
    {
        "name": "Сценарий: Подбор офисного кресла для руководителя",
        "steps": [
            {
                "question": "Нужно солидное офисное кресло для директора.",
                "expected_keywords": ["директор премиум", "кожа наппа", "алюминиевого"]
            },
            {
                "question": "А что-нибудь в классическом стиле, не слишком дорогое?",
                "expected_keywords": ["женева", "массив бука", "классическ"]
            },
            {
                "question": "Сколько оно стоит?",
                "expected_keywords": ["67000", "рублей"]
            }
        ]
    }
]


async def run_single_test(agent: Agent, test_case: dict, session_id: str) -> bool:
    """Запускает один тестовый случай и возвращает результат."""
    question = test_case["question"]
    expected_keywords = test_case["expected_keywords"]

    logger.info(f"▶️  Запуск теста: '{test_case['name']}'")
    logger.info(f"   - Вопрос: \"{question}\"")

    response_generator = agent.get_response_generator(question, session_id)

    full_response = ""
    for chunk in response_generator:
        if chunk:
            full_response += chunk

    full_response_lower = full_response.lower()
    logger.info(f"   - Ответ бота: \"{full_response.strip()}\"")

    missing_keywords = [kw for kw in expected_keywords if kw.lower() not in full_response_lower]

    if not missing_keywords:
        logger.info(f"   ✅ ТЕСТ ПРОЙДЕН\n")
        return True
    else:
        logger.error(f"   ❌ ТЕСТ ПРОВАЛЕН. Не найдены ключевые слова: {missing_keywords}\n")
        return False

async def run_scenario_test(agent: Agent, test_case: dict, session_id: str) -> bool:
    """Запускает один сценарный тест и возвращает результат."""
    logger.info(f"▶️  Запуск сценария: '{test_case['name']}'")
    scenario_passed = True

    for i, step in enumerate(test_case["steps"]):
        question = step["question"]
        expected_keywords = step["expected_keywords"]
        logger.info(f"   - Шаг {i+1}: \"{question}\"")

        response_generator = agent.get_response_generator(question, session_id)

        step_response = ""
        for chunk in response_generator:
            if chunk:
                step_response += chunk

        step_response_lower = step_response.lower()
        logger.info(f"   - Ответ бота: \"{step_response.strip()}\"")

        missing_keywords = [kw for kw in expected_keywords if kw.lower() not in step_response_lower]

        if missing_keywords:
            logger.error(f"   ❌ ШАГ {i+1} ПРОВАЛЕН. Не найдены слова: {missing_keywords}")
            scenario_passed = False
        else:
            logger.info(f"   ✅ Шаг {i+1} пройден.")

    if scenario_passed:
        logger.info(f"   ✅ СЦЕНАРИЙ ПРОЙДЕН\n")
        return True
    else:
        logger.error(f"   ❌ СЦЕНАРИЙ ПРОВАЛЕН.\n")
        return False


async def main():
    """Основная функция для запуска всех тестов."""
    load_dotenv()

    logger.info("="*50)
    logger.info("🚀 НАЧАЛО ТЕСТИРОВАНИЯ AI-АГЕНТА 🚀")
    logger.info("="*50)

    try:
        agent = Agent()
    except Exception as e:
        logger.critical(f"Не удалось инициализировать агента: {e}", exc_info=True)
        return

    results = {"passed": 0, "failed": 0}
    total_tests = len(SINGLE_CASES) + len(SCENARIO_CASES)

    # Запуск одиночных тестов
    logger.info("\n--- ОДИНОЧНЫЕ ТЕСТЫ ---\n")
    for test_case in SINGLE_CASES:
        session_id = f"test-session-{uuid.uuid4()}" # Новый диалог для каждого теста
        is_passed = await run_single_test(agent, test_case, session_id)
        if is_passed:
            results["passed"] += 1
        else:
            results["failed"] += 1

    # Запуск сценарных тестов
    logger.info("\n--- СЦЕНАРНЫЕ ТЕСТЫ (КОНТЕКСТ) ---\n")
    for test_case in SCENARIO_CASES:
        session_id = f"test-session-{uuid.uuid4()}" # Новый диалог для каждого сценария
        is_passed = await run_scenario_test(agent, test_case, session_id)
        if is_passed:
            results["passed"] += 1
        else:
            results["failed"] += 1

    logger.info("="*50)
    logger.info("🏁 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО 🏁")
    logger.info("="*50)
    logger.info(f"📊 РЕЗУЛЬТАТЫ:")
    logger.info(f"   - ✅ Пройдено: {results['passed']} из {total_tests}")
    logger.info(f"   - ❌ Провалено: {results['failed']} из {total_tests}")
    logger.info("="*50)

    if results["failed"] > 0:
        logger.warning("Некоторые тесты не были пройдены. Проверьте логи выше.")
        sys.exit(1) # Выходим с кодом ошибки, если есть проваленные тесты
    else:
        logger.info("🎉 Все тесты успешно пройдены!")


if __name__ == "__main__":
    # Для Windows может потребоваться другая политика
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
