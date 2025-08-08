from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_history_aware_retriever
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
import logging
import json
import os

load_dotenv()

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self) -> None:
        logger.info("--- Инициализация Агента 'Метротест' ---")
        self.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.2, streaming=True)
        self.store = {}
        self.last_kb = "general"
        try:
            self.prompts = self.load_prompts()
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать агента из-за проблемы с конфигурацией промптов. {e}", exc_info=True)
            # Прерываем выполнение, чтобы предотвратить запуск с неверной конфигурацией
            raise SystemExit(f"Остановка приложения: {e}")

        self._initialize_rag_chain()
        logger.info("--- Агент 'Метротест' успешно инициализирован ---")

    def load_prompts(self):
        prompts_file = os.getenv("PROMPTS_FILE_PATH")
        if not prompts_file:
            raise ValueError("Переменная окружения PROMPTS_FILE_PATH не установлена.")

        logger.info(f"Загрузка промптов из файла: '{prompts_file}'")
        try:
            with open(prompts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл промптов не найден по пути: {prompts_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON в файле {prompts_file}: {e}")
            raise

    def _initialize_rag_chain(self):
        """Инициализирует или перезагружает компоненты RAG."""
        logger.info("Инициализация или перезагрузка RAG-цепочки...")

        persist_directory = os.getenv("PERSIST_DIRECTORY")
        if not persist_directory:
             raise ValueError("Переменная окружения PERSIST_DIRECTORY не установлена.")

        logger.info(f"Подключение к векторной базе в '{persist_directory}'...")
        embeddings = OpenAIEmbeddings(chunk_size=1000)
        self.db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        # Два ретривера по метаданным, меньший k для скорости
        kb_k = int(os.getenv("KB_TOP_K", "3"))
        self.retriever_general = self.db.as_retriever(
            search_type="similarity", search_kwargs={"k": kb_k, "filter": {"kb": "general"}}
        )
        self.retriever_tech = self.db.as_retriever(
            search_type="similarity", search_kwargs={"k": kb_k, "filter": {"kb": "tech"}}
        )
        logger.info("Подключение к базе данных успешно.")

        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [("system", self.prompts["contextualize_q_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        # Историзованные ретриверы для обеих БЗ
        history_aware_retriever_general = create_history_aware_retriever(self.llm, self.retriever_general, contextualize_q_prompt)
        history_aware_retriever_tech = create_history_aware_retriever(self.llm, self.retriever_tech, contextualize_q_prompt)

        qa_prompt = ChatPromptTemplate.from_messages(
            [("system", self.prompts["qa_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        question_answer_chain = create_stuff_documents_chain(self.llm, qa_prompt)

        rag_chain_general = create_retrieval_chain(history_aware_retriever_general, question_answer_chain)
        rag_chain_tech = create_retrieval_chain(history_aware_retriever_tech, question_answer_chain)

        self.conversational_rag_chain_general = RunnableWithMessageHistory(
            rag_chain_general,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )
        self.conversational_rag_chain_tech = RunnableWithMessageHistory(
            rag_chain_tech,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )
        logger.info("--- RAG-цепочка успешно создана/обновлена ---")

    def _route_kb(self, text: str) -> str:
        """Простая и быстрая маршрутизация: general | tech.
        Выбираем 'tech', если обнаружены технические маркеры; иначе 'general'."""
        if not text:
            return "general"
        t = text.lower()
        tech_markers = [
            "техн", "характерист", "параметр", "диапазон", "класс точности", "нагруз", "датчик",
            "тензо", "разрывн", "машин", "усилие", "кн", "мпа", "ньютон", "мм", "гост", "iso",
            "сертиф", "модуль", "частота", "вибро", "сопротивл", "протокол", "datasheet", "spec"
        ]
        general_markers = ["цена", "стоимость", "контакт", "гарант", "доставка", "оплата", "адрес"]
        if any(m in t for m in tech_markers) and not any(m in t for m in general_markers):
            return "tech"
        return "general"

    def _max_relevance(self, question: str, kb: str, k: int) -> float:
        try:
            # Для оценки порога берём релевантность напрямую из векторного стора
            res = self.db.similarity_search_with_relevance_scores(
                question, k=k, filter={"kb": kb}
            )
            if not res:
                return 0.0
            return max(score for _, score in res)
        except Exception:
            return 1.0  # если стор не вернул оценку, не триггерим фолбэк

    def reload(self):
        """Перезагружает промпты, векторную базу данных и RAG-цепочку."""
        logger.info("🔃 Получена команда на перезагрузку агента...")
        try:
            self.prompts = self.load_prompts()
            self._initialize_rag_chain()
            logger.info("✅ Агент успешно перезагружен с новой базой знаний и промптами.")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при перезагрузке агента: {e}", exc_info=True)
            return False

    def get_session_history(self, session_id: str):
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
        return self.store[session_id]

    def get_response_generator(self, user_question: str, session_id: str):
        target = self._route_kb(user_question)
        # Порог и k берём из env (по умолчанию 0.2 и 3)
        threshold = float(os.getenv("KB_FALLBACK_THRESHOLD", "0.2"))
        k = int(os.getenv("KB_TOP_K", "3"))
        # Оценим релевантность выбранной БЗ; при низкой — попробуем вторую
        max_score = self._max_relevance(user_question, target, k)
        alt = "tech" if target == "general" else "general"
        if max_score < threshold:
            alt_score = self._max_relevance(user_question, alt, k)
            if alt_score > max_score:
                logger.info(
                    f"Низкая релевантность ({max_score:.2f}) для {target} → переключаемся на {alt} ({alt_score:.2f})"
                )
                target = alt
        self.last_kb = target
        logger.info(f"Маршрутизация вопроса в БЗ: {target}")
        chain = self.conversational_rag_chain_tech if target == "tech" else self.conversational_rag_chain_general
        stream = chain.stream(
            {"input": user_question},
            config={"configurable": {"session_id": session_id}},
        )
        for chunk in stream:
            if 'answer' in chunk:
                yield chunk['answer']
