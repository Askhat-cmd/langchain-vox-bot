"""
Скрипт для создания векторной базы данных ChromaDB
из текстового файла базы знаний.
"""
import os
import re
import shutil
import logging
from dotenv import load_dotenv

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Загрузка переменных окружения ---
load_dotenv()

# --- Константы из .env ---
KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "knowledge_base.md")
PERSIST_DIRECTORY = os.getenv("PERSIST_DIRECTORY", "chroma_db_metrotech")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    logging.error("Не найден ключ OPENAI_API_KEY в .env файле.")
    exit()

def duplicate_headers_without_hashes(text: str) -> str:
    """
    Дублирует заголовки Markdown (от h1 до h6) в тексте,
    добавляя версию без хэшей в следующей строке.
    Это обогащает контекст для каждого чанка.
    """
    def replacer(match):
        header_line = match.group(0)
        # Убираем хэши и лишние пробелы, чтобы получить чистый заголовок
        clean_header = header_line.lstrip('#').strip()
        # Возвращаем исходный заголовок и чистый заголовок на новой строке
        return f"{header_line}\n{clean_header}"

    # Используем re.MULTILINE для обработки каждой строки
    processed_text = re.sub(r"^(#{1,6}\s.+)", replacer, text, flags=re.MULTILINE)
    return processed_text

def create_embeddings():
    """
    Основная функция для создания и сохранения векторных представлений.
    """
    if not os.path.exists(KNOWLEDGE_BASE_PATH):
        logging.error(f"Файл базы знаний не найден по пути: {KNOWLEDGE_BASE_PATH}")
        return False

    logging.info(f"Чтение базы знаний из файла: {KNOWLEDGE_BASE_PATH}")
    try:
        with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as file:
            full_text = file.read()
    except Exception as e:
        logging.error(f"Ошибка при чтении файла: {e}")
        return False

    # 1. Сначала обогащаем весь текст дубликатами заголовков
    logging.info("Обогащение текста: дублирование заголовков для улучшения контекста...")
    enriched_text = duplicate_headers_without_hashes(full_text)
    logging.info("Текст успешно обогащен.")

    # 2. Затем разделяем текст на чанки по кастомному разделителю '<<->>'
    logging.info("Разделение текста на чанки по кастомному разделителю '<<->>'...")
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["<<->>"], # Указываем наш уникальный разделитель
        chunk_size=4000, # Устанавливаем большой размер чанка, т.к. делим вручную
        chunk_overlap=200, # Небольшое перекрытие на всякий случай
        add_start_index=True,
    )
    documents = text_splitter.create_documents([enriched_text])

    if not documents:
        logging.warning("Не удалось создать ни одного чанка. Проверьте наличие разделителей '<<->>' в файле.")
        return False

    logging.info(f"Текст разделен на {len(documents)} чанков.")

    # --- Создание и сохранение эмбеддингов ---
    logging.info(f"Инициализация OpenAI Embeddings...")
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

    # Если директория для ChromaDB уже существует, удаляем ее для полного обновления
    if os.path.exists(PERSIST_DIRECTORY):
        logging.info(f"Удаление старой базы данных из директории: {PERSIST_DIRECTORY}")
        shutil.rmtree(PERSIST_DIRECTORY)

    logging.info(f"Создание новой векторной базы данных в {PERSIST_DIRECTORY}...")
    db = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=PERSIST_DIRECTORY
    )
    logging.info("Векторная база данных успешно создана и сохранена.")
    return True


def recreate_embeddings():
    """Функция-обертка для вызова из других модулей."""
    logging.info("Запрошено пересоздание эмбеддингов...")
    return create_embeddings()

if __name__ == "__main__":
    create_embeddings()
