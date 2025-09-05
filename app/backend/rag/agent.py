from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_chroma import Chroma
from dotenv import load_dotenv
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
import logging
import json
import os
import redis
import hashlib
import time
from typing import List

class CachedOpenAIEmbeddings(OpenAIEmbeddings):
    """Кешированные OpenAI Embeddings для ускорения повторных запросов"""
    
    def __init__(self, redis_client, **kwargs):
        super().__init__(**kwargs)
        # Используем объект для хранения кеш-данных
        self._cache_data = {
            'redis_client': redis_client,
            'cache_prefix': "embedding_cache:",
            'cache_ttl': 3600 * 24 * 7  # 7 дней
        }
        
    def _get_cache_key(self, text: str) -> str:
        """Генерирует ключ кеша для текста"""
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"{self._cache_data['cache_prefix']}{text_hash}"
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Кешированное создание embeddings для документов"""
        results = []
        texts_to_embed = []
        text_indices = []
        
        # Проверяем кеш для каждого текста
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached_embedding = self._cache_data['redis_client'].get(cache_key)
            
            if cached_embedding:
                # Восстанавливаем embedding из кеша
                embedding = json.loads(cached_embedding)
                results.append(embedding)
                logger.debug(f"✅ Embedding из кеша для текста {i}")
            else:
                # Добавляем в список для создания embedding
                texts_to_embed.append(text)
                text_indices.append(i)
                results.append(None)  # Заглушка
        
        # Создаем embeddings для текстов, которых нет в кеше
        if texts_to_embed:
            logger.info(f"🔄 Создаем {len(texts_to_embed)} новых embeddings")
            new_embeddings = super().embed_documents(texts_to_embed)
            
            # Сохраняем в кеш и заполняем результаты
            for i, (text, embedding) in enumerate(zip(texts_to_embed, new_embeddings)):
                cache_key = self._get_cache_key(text)
                self._cache_data['redis_client'].setex(cache_key, self._cache_data['cache_ttl'], json.dumps(embedding))
                
                # Заполняем результат
                original_index = text_indices[i]
                results[original_index] = embedding
                logger.debug(f"💾 Сохранен в кеш embedding для текста {original_index}")
        
        return results
    
    def embed_query(self, text: str) -> List[float]:
        """Кешированное создание embedding для запроса"""
        cache_key = self._get_cache_key(text)
        cached_embedding = self._cache_data['redis_client'].get(cache_key)
        
        if cached_embedding:
            logger.debug("✅ Embedding запроса из кеша")
            return json.loads(cached_embedding)
        
        # Создаем новый embedding
        logger.debug("🔄 Создаем новый embedding для запроса")
        embedding = super().embed_query(text)
        
        # Сохраняем в кеш
        self._cache_data['redis_client'].setex(cache_key, self._cache_data['cache_ttl'], json.dumps(embedding))
        logger.debug("💾 Сохранен в кеш embedding запроса")
        
        return embedding

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
        
        # НОВОЕ: Redis кеширование для embeddings
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
            self.redis_client.ping()  # проверяем соединение
            self.cache_enabled = True
            logger.info("✅ Redis кеширование включено")
        except Exception as e:
            self.redis_client = None
            self.cache_enabled = False
            logger.warning(f"⚠️ Redis недоступен, кеширование отключено: {e}")
        try:
            self.prompts = self.load_prompts()
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать агента из-за проблемы с конфигурацией промптов. {e}", exc_info=True)
            # Прерываем выполнение, чтобы предотвратить запуск с неверной конфигурацией
            raise SystemExit(f"Остановка приложения: {e}")

        self._initialize_rag_chain()
        logger.info("--- Агент 'Метротест' успешно инициализирован ---")

    def _get_cache_key(self, text: str, kb: str) -> str:
        """Генерирует ключ кеша для embedding запроса."""
        combined = f"{text}:{kb}:{self.last_kb}"
        return f"emb:{hashlib.md5(combined.encode()).hexdigest()}"
    
    def _get_cached_documents(self, text: str, kb: str):
        """Получает кешированные документы из Redis."""
        if not self.cache_enabled:
            return None
        
        cache_key = self._get_cache_key(text, kb)
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                logger.info(f"🎯 КЕШИРОВАНИЕ: Используем кешированный поиск для: {text[:30]}...")
                return json.loads(cached)
        except Exception as e:
            logger.debug(f"Ошибка чтения кеша: {e}")
        return None
    
    def _cache_documents(self, text: str, kb: str, documents):
        """Кеширует результаты поиска в Redis."""
        if not self.cache_enabled or not documents:
            return
            
        cache_key = self._get_cache_key(text, kb)
        try:
            # Кешируем на 1 час
            doc_contents = [{"content": doc.page_content, "metadata": doc.metadata} for doc in documents]
            self.redis_client.setex(
                cache_key, 
                3600,  # 1 час TTL
                json.dumps(doc_contents)
            )
            logger.debug(f"📦 КЕШИРОВАНИЕ: Сохранили {len(documents)} документов в кеш")
        except Exception as e:
            logger.debug(f"Ошибка записи в кеш: {e}")

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
        return ChatOpenAI(
            model_name=model_name, 
            temperature=temperature, 
            streaming=True,
            request_timeout=15,  # ОПТИМИЗАЦИЯ: агрессивный timeout для запросов
            max_retries=1        # ОПТИМИЗАЦИЯ: минимум повторов
        )

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
        
        # ОПТИМИЗАЦИЯ: Создаем кешированные embeddings
        if self.cache_enabled:
            embeddings = CachedOpenAIEmbeddings(
                redis_client=self.redis_client,
                chunk_size=1000
            )
            logger.info("✅ Используем кешированные embeddings")
        else:
            embeddings = OpenAIEmbeddings(chunk_size=1000)
            logger.info("⚠️ Используем обычные embeddings (кеширование недоступно)")
            
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
        # ОПТИМИЗАЦИЯ: Убираем history_aware_retriever для ускорения
        # Вместо дополнительного LLM запроса для контекстуализации, используем простые retriever'ы
        logger.info("🚀 ОПТИМИЗАЦИЯ: Используем простые retriever'ы без history_aware для ускорения")
        
        qa_prompt = ChatPromptTemplate.from_messages(
            [("system", self.prompts["qa_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

        # Используем простые retriever'ы вместо history_aware
        rag_chain_general = create_retrieval_chain(self.retriever_general, question_answer_chain)
        rag_chain_tech = create_retrieval_chain(self.retriever_tech, question_answer_chain)

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

# УДАЛЕНА МЕДЛЕННАЯ ФУНКЦИЯ _max_relevance() - она тратила 6.4 секунды!
    # Эта функция отсутствовала в быстрой Voximplant версии

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
        import time
        start_time = time.time()
        logger.info(f"🕐 ПРОФИЛИРОВАНИЕ: Начало get_response_generator для вопроса: '{user_question[:50]}...'")
        
        # УПРОЩЕННАЯ маршрутизация (как в Voximplant версии)
        route_start = time.time()
        target = self._route_kb(user_question)
        route_time = time.time() - route_start
        logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Маршрутизация заняла {route_time:.3f}с")
        
        # УБИРАЕМ МЕДЛЕННУЮ ОЦЕНКУ РЕЛЕВАНТНОСТИ!
        # Была: max_score = self._max_relevance() - 6.4 секунды!
        # Теперь: просто используем результат маршрутизации
        
        self.last_kb = target
        logger.info(f"Маршрутизация вопроса в БЗ: {target}")
        
        setup_time = time.time() - start_time
        logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Общая подготовка заняла {setup_time:.3f}с")
        def _stream_with_chain(use_fallback: bool):
            import time
            stream_start = time.time()
            logger.info(f"🔄 ПРОФИЛИРОВАНИЕ: Начинаем streaming с {'FALLBACK' if use_fallback else 'PRIMARY'} моделью")
            
            chain_local = (
                self.conversational_rag_chain_tech if target == "tech" else self.conversational_rag_chain_general
            )
            
            chain_setup_time = time.time() - stream_start
            logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Подготовка цепочки заняла {chain_setup_time:.3f}с")
            
            stream_call_start = time.time()
            stream_local = chain_local.stream(
                {"input": user_question},
                config={"configurable": {"session_id": session_id}},
            )
            stream_call_time = time.time() - stream_call_start
            logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Вызов stream() занял {stream_call_time:.3f}с")
            
            first_chunk = True
            chunk_count = 0
            for chunk in stream_local:
                if first_chunk:
                    first_chunk_time = time.time() - stream_start
                    logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Первый чанк получен через {first_chunk_time:.3f}с")
                    first_chunk = False
                
                if 'answer' in chunk:
                    chunk_count += 1
                    yield chunk['answer']
            
            total_stream_time = time.time() - stream_start
            logger.info(f"⏱️ ПРОФИЛИРОВАНИЕ: Весь streaming занял {total_stream_time:.3f}с, чанков: {chunk_count}")

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
