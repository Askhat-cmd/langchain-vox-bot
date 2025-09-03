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
        # Текущая LLM и ленивый fallback
        self.llm = self._create_llm_from_env(primary=True)
        self.fallback_llm = None
        self._fallback_chains_built = False
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

    def _create_llm_from_env(self, primary: bool) -> ChatOpenAI:
        """Создаёт LLM на основе переменных окружения.
        primary=True → LLM_MODEL_PRIMARY, иначе LLM_MODEL_FALLBACK.
        """
        model_env_key = "LLM_MODEL_PRIMARY" if primary else "LLM_MODEL_FALLBACK"
        model_name = os.getenv(model_env_key, os.getenv("LLM_MODEL_PRIMARY", "gpt-4o-mini"))
        try:
            temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
        except ValueError:
            temperature = 0.2
        logger.info(f"LLM конфигурация: {'PRIMARY' if primary else 'FALLBACK'} model='{model_name}', temperature={temperature}")
        return ChatOpenAI(model_name=model_name, temperature=temperature, streaming=True)

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
        """Инициализирует/перезагружает векторное хранилище и RAG-цепочки для текущей LLM."""
        logger.info("Инициализация или перезагрузка RAG-цепочки...")

        persist_directory = os.getenv("PERSIST_DIRECTORY")
        if not persist_directory:
            raise ValueError("Переменная окружения PERSIST_DIRECTORY не установлена.")

        logger.info(f"Подключение к векторной базе в '{persist_directory}'...")
        embeddings = OpenAIEmbeddings(chunk_size=1000)
        self.db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        kb_k = int(os.getenv("KB_TOP_K", "3"))
        self.retriever_general = self.db.as_retriever(
            search_type="similarity", search_kwargs={"k": kb_k, "filter": {"kb": "general"}}
        )
        self.retriever_tech = self.db.as_retriever(
            search_type="similarity", search_kwargs={"k": kb_k, "filter": {"kb": "tech"}}
        )
        logger.info("Подключение к базе данных успешно.")

        # Строим цепочки для текущей LLM
        self._build_chains_for_llm(self.llm)
        # Сбросим кэш фолбэка
        self._fallback_chains_built = False
        self.fallback_llm = None
        logger.info("--- RAG-цепочка успешно создана/обновлена ---")

    def _build_chains_for_llm(self, llm: ChatOpenAI):
        """Строит и сохраняет цепочки для указанной LLM."""
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [("system", self.prompts["contextualize_q_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        history_aware_retriever_general = create_history_aware_retriever(llm, self.retriever_general, contextualize_q_prompt)
        history_aware_retriever_tech = create_history_aware_retriever(llm, self.retriever_tech, contextualize_q_prompt)

        qa_prompt = ChatPromptTemplate.from_messages(
            [("system", self.prompts["qa_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

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
            # Обновим конфигурацию моделей
            self.llm = self._create_llm_from_env(primary=True)
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
        def _stream_with_chain(use_fallback: bool):
            chain_local = (
                self.conversational_rag_chain_tech if target == "tech" else self.conversational_rag_chain_general
            )
            stream_local = chain_local.stream(
                {"input": user_question},
                config={"configurable": {"session_id": session_id}},
            )
            for chunk in stream_local:
                if 'answer' in chunk:
                    yield chunk['answer']

        def _invoke_non_streaming_with_llm(model_name: str):
            """Локально построить НЕстриминговые цепочки под указанный model_name и вернуть полный ответ одной строкой."""
            try:
                temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
            except ValueError:
                temperature = 0.2
            llm_local = ChatOpenAI(model_name=model_name, temperature=temperature, streaming=False)

            contextualize_q_prompt = ChatPromptTemplate.from_messages(
                [("system", self.prompts["contextualize_q_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
            )
            history_aware_retriever_general = create_history_aware_retriever(llm_local, self.retriever_general, contextualize_q_prompt)
            history_aware_retriever_tech = create_history_aware_retriever(llm_local, self.retriever_tech, contextualize_q_prompt)

            qa_prompt = ChatPromptTemplate.from_messages(
                [("system", self.prompts["qa_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
            )
            question_answer_chain = create_stuff_documents_chain(llm_local, qa_prompt)

            rag_chain_local = create_retrieval_chain(
                history_aware_retriever_tech if target == "tech" else history_aware_retriever_general,
                question_answer_chain,
            )
            runnable = RunnableWithMessageHistory(
                rag_chain_local,
                self.get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
                output_messages_key="answer",
            )
            result = runnable.invoke(
                {"input": user_question},
                config={"configurable": {"session_id": session_id}},
            )
            text = result.get("answer", "")
            if text:
                yield text

        # Попробуем основной пайплайн; при ошибке — один раз фолбэк на запасную модель
        try:
            yield from _stream_with_chain(use_fallback=False)
        except Exception as e:
            fb_model = os.getenv("LLM_MODEL_FALLBACK")
            primary_model = os.getenv("LLM_MODEL_PRIMARY", "gpt-4o-mini")
            err_text = str(e).lower()
            # Если стрим запрещён организацией/моделью — попробуем НЕстриминговый режим на основной модели
            if "unsupported_value" in err_text or "verify organization" in err_text or "param': 'stream" in err_text:
                logger.warning("Стриминг недоступен для текущей организации/модели → переключаемся на НЕстриминговый режим (PRIMARY)")
                try:
                    yield from _invoke_non_streaming_with_llm(primary_model)
                    return
                except Exception as e_ns:
                    logger.error(f"Не удалось выполнить нестриминговый режим на PRIMARY: {e_ns}", exc_info=True)
            # Если фолбэк определён — попробуем его (стрим), затем НЕстримингово
            if not fb_model or fb_model == primary_model:
                logger.error(f"Ошибка генерации (без фолбэка): {e}", exc_info=True)
                return
            logger.warning(f"Основная модель упала: {e}. Пытаемся переключиться на FALLBACK '{fb_model}'…")
            # Построим цепочки для fallback один раз
            try:
                if not self._fallback_chains_built:
                    self.fallback_llm = self._create_llm_from_env(primary=False)
                    self._build_chains_for_llm(self.fallback_llm)
                    self._fallback_chains_built = True
                try:
                    yield from _stream_with_chain(use_fallback=True)
                    return
                except Exception as e_fb_stream:
                    logger.warning(f"Фолбэк в стриминговом режиме не удался: {e_fb_stream}. Пробуем НЕстримингово…")
                    yield from _invoke_non_streaming_with_llm(fb_model)
            except Exception as e2:
                logger.error(f"Фолбэк модель также не справилась: {e2}", exc_info=True)
                return
