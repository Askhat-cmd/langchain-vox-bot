import os
import re
import logging
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import MarkdownHeaderTextSplitter
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def duplicate_headers_without_hashes(text: str) -> str:
    """
    Дублирует заголовки Markdown (от h1 до h6) в тексте,
    добавляя версию без хэшей в следующей строке.
    Это обогащает чанки, сохраняя заголовок в самом тексте.

    Например:
    '## Заголовок' превращается в:
    '## Заголовок
    Заголовок'
    """
    # Функция для замены, которая будет вызвана для каждого найденного заголовка
    def replacer(match):
        header_line = match.group(0)
        # Удаляем хэши и лишние пробелы, чтобы получить чистый заголовок
        clean_header = header_line.lstrip('#').strip()
        # Возвращаем исходный заголовок, перенос строки и чистый заголовок
        return f"{header_line}\n{clean_header}"

    # Regex для поиска заголовков от 1 до 6 уровня, которые находятся в начале строки
    processed_text = re.sub(r"^(#{1,6}\s.+)", replacer, text, flags=re.MULTILINE)
    return processed_text

def recreate_embeddings():
    """
    Основная функция для создания и сохранения векторной базы данных.
    Читает пути из переменных окружения.
    """
    load_dotenv()
    logging.info("--- Начало процесса создания эмбеддингов ---")

    knowledge_base_path = os.getenv("KNOWLEDGE_BASE_PATH")
    persist_directory = os.getenv("PERSIST_DIRECTORY")

    if not knowledge_base_path or not persist_directory:
        logging.critical("КРИТИЧЕСКАЯ ОШИБКА: Переменные окружения KNOWLEDGE_BASE_PATH и PERSIST_DIRECTORY должны быть установлены.")
        return False

    # Используем абсолютный путь к корневой директории проекта
    project_root = os.path.dirname(os.path.abspath(__file__))
    source_document_path = os.path.join(project_root, knowledge_base_path)
    db_directory = os.path.join(project_root, persist_directory)


    logging.info(f"1/5: Загрузка документа из '{source_document_path}'...")
    if not os.path.exists(source_document_path):
        logging.error(f"Файл '{source_document_path}' не найден.")
        return False

    with open(source_document_path, 'r', encoding='utf-8') as f:
        markdown_document = f.read()
    logging.info("Документ успешно загружен.")

    logging.info("2/5: Дублирование заголовков для обогащения чанков...")
    enriched_document = duplicate_headers_without_hashes(markdown_document)
    logging.info("Заголовки успешно продублированы.")


    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
    ]

    logging.info("3/5: Разделение текста на чанки по заголовкам Markdown...")
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
    texts = markdown_splitter.split_text(enriched_document)
    logging.info(f"Текст разделен на {len(texts)} чанков.")

    logging.info("4/5: Инициализация модели эмбеддингов OpenAI...")
    embeddings = OpenAIEmbeddings(chunk_size=1000)
    logging.info("Модель инициализирована.")

    logging.info(f"5/5: Создание и сохранение векторной базы в папку '{db_directory}'...")
    db = Chroma.from_documents(
        texts,
        embeddings,
        persist_directory=db_directory
    )
    logging.info("--- Процесс успешно завершен! ---")
    logging.info(f"Ваша база знаний готова для использования в папке '{db_directory}'.")
    return True

def main_cli():
    """
    Функция для запуска из командной строки.
    """
    recreate_embeddings()

if __name__ == "__main__":
    main_cli()
