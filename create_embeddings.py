import os
import logging
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def recreate_embeddings():
    """
    Основная функция для создания и сохранения векторной базы данных.
    """
    load_dotenv()
    logging.info("--- Начало процесса создания эмбеддингов ---")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_document_path = os.path.join(script_dir, "Метротест_САЙТ.txt")
    persist_directory = os.path.join(script_dir, "chroma_db_metrotech")
    chunk_size = 1000
    chunk_overlap = 200

    logging.info(f"1/4: Загрузка документа из '{source_document_path}'...")
    if not os.path.exists(source_document_path):
        logging.error(f"Файл '{source_document_path}' не найден.")
        return

    loader = TextLoader(source_document_path, encoding='utf-8')
    documents = loader.load()
    logging.info(f"Документ успешно загружен. Количество страниц: {len(documents)}")

    logging.info(f"2/4: Разделение текста на чанки (размер: {chunk_size}, перекрытие: {chunk_overlap})...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    texts = text_splitter.split_documents(documents)
    logging.info(f"Текст разделен на {len(texts)} чанков.")

    logging.info("3/4: Инициализация модели эмбеддингов OpenAI...")
    embeddings = OpenAIEmbeddings(chunk_size=1000)
    logging.info("Модель инициализирована.")

    logging.info(f"4/4: Создание и сохранение векторной базы в папку '{persist_directory}'...")
    db = Chroma.from_documents(
        texts,
        embeddings,
        persist_directory=persist_directory
    )
    logging.info("--- Процесс успешно завершен! ---")
    logging.info(f"Ваша база знаний готова для использования в папке '{persist_directory}'.")
    return True

def main_cli():
    """
    Функция для запуска из командной строки.
    """
    recreate_embeddings()

if __name__ == "__main__":
    main_cli()
