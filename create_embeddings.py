# create_embeddings.py
import os
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from dotenv import load_dotenv

# Загружаем переменные окружения (должен быть OPENAI_API_KEY,
# а также HTTP_PROXY и HTTPS_PROXY, если они нужны)
print("Загрузка переменных окружения из .env файла...")
load_dotenv()
print("Переменные окружения загружены.")
# Библиотеки openai и httpx автоматически используют переменные HTTP_PROXY и HTTPS_PROXY,
# если они установлены в окружении. Ручная настройка клиента не требуется.

# --- Конфигурация ---
# 1. Путь к файлу с базой знаний
script_dir = os.path.dirname(os.path.abspath(__file__))
SOURCE_DOCUMENT_PATH = os.path.join(script_dir, "Метротест_САЙТ.txt")
# 2. Название папки, куда будут сохранены эмбеддинги
PERSIST_DIRECTORY = os.path.join(script_dir, "chroma_db_metrotech")
# 3. Размер одного чанка (в символах)
CHUNK_SIZE = 1000
# 4. Перекрытие между чанками (чтобы не терять контекст на стыках)
CHUNK_OVERLAP = 200

def main():
    """
    Основная функция для создания и сохранения векторной базы данных.
    """
    print("--- Начало процесса создания эмбеддингов ---")

    # 1. Загрузка документа
    print(f"1/4: Загрузка документа из '{SOURCE_DOCUMENT_PATH}'...")
    if not os.path.exists(SOURCE_DOCUMENT_PATH):
        print(f"Ошибка: Файл '{SOURCE_DOCUMENT_PATH}' не найден.")
        return
        
    loader = TextLoader(SOURCE_DOCUMENT_PATH, encoding='utf-8')
    documents = loader.load()
    print(f"Документ успешно загружен. Количество страниц: {len(documents)}")

    # 2. Разделение текста на чанки
    print(f"2/4: Разделение текста на чанки (размер: {CHUNK_SIZE}, перекрытие: {CHUNK_OVERLAP})...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    texts = text_splitter.split_documents(documents)
    print(f"Текст разделен на {len(texts)} чанков.")

    # 3. Инициализация модели для создания эмбеддингов
    print("3/4: Инициализация модели эмбеддингов OpenAI...")
    # Ручная передача http_client не нужна, библиотека подхватит прокси из окружения
    embeddings = OpenAIEmbeddings(chunk_size=1000)
    print("Модель инициализирована.")

    # 4. Создание и сохранение векторной базы данных
    print(f"4/4: Создание и сохранение векторной базы в папку '{PERSIST_DIRECTORY}'...")
    db = Chroma.from_documents(
        texts, 
        embeddings, 
        persist_directory=PERSIST_DIRECTORY
    )
    print("--- Процесс успешно завершен! ---")
    print(f"Ваша база знаний готова для использования в папке '{PERSIST_DIRECTORY}'.")


if __name__ == "__main__":
    main()
