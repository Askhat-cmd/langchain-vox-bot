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

load_dotenv()

PERSIST_DIRECTORY = "chroma_db_metrotech"
PROMPTS_FILE = "prompts.json"
logger = logging.getLogger(__name__)

class Agent:
    def __init__(self) -> None:
        logger.info("--- Инициализация Агента 'Метротест' ---")
        self.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.2, streaming=True)
        self.store = {}
        self.prompts = self.load_prompts()
        self._initialize_rag_chain()
        logger.info("--- Агент 'Метротест' успешно инициализирован ---")

    def load_prompts(self):
        try:
            with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Не удалось загрузить промпты из {PROMPTS_FILE}: {e}")
            # Возвращаем дефолтные значения в случае ошибки
            return {
                "contextualize_q_system_prompt": "...",
                "qa_system_prompt": "..."
            }

    def _initialize_rag_chain(self):
        """Инициализирует или перезагружает компоненты RAG."""
        logger.info("Инициализация или перезагрузка RAG-цепочки...")
        
        logger.info(f"Подключение к векторной базе в '{PERSIST_DIRECTORY}'...")
        embeddings = OpenAIEmbeddings(chunk_size=1000)
        self.db = Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings)
        self.retriever = self.db.as_retriever(search_type="mmr", search_kwargs={"k": 5})
        logger.info("Подключение к базе данных успешно.")
        
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [("system", self.prompts["contextualize_q_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        history_aware_retriever = create_history_aware_retriever(self.llm, self.retriever, contextualize_q_prompt)

        qa_prompt = ChatPromptTemplate.from_messages(
            [("system", self.prompts["qa_system_prompt"]), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        question_answer_chain = create_stuff_documents_chain(self.llm, qa_prompt)
        
        rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
        
        self.conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )
        logger.info("--- RAG-цепочка успешно создана/обновлена ---")

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
        stream = self.conversational_rag_chain.stream(
            {"input": user_question},
            config={"configurable": {"session_id": session_id}},
        )
        for chunk in stream:
            if 'answer' in chunk:
                yield chunk['answer']
