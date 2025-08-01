from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_history_aware_retriever
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

load_dotenv()

PERSIST_DIRECTORY = "chroma_db_metrotech"

# Промпт для переформулирования вопроса с учетом истории
contextualize_q_system_prompt = """Учитывая историю чата и последний вопрос пользователя, который может ссылаться на контекст в истории чата, \
сформулируй самостоятельный вопрос, который можно понять без истории чата. НЕ отвечай на вопрос, \
просто переформулируй его, если это необходимо, в противном случае верни его как есть."""

# Основной системный промпт для ответа (без саммаризации)
qa_system_prompt = """
Ты — русскоязычный нейро-консультант "Метротэст".
- Отвечай вежливо, профессионально и по делу, основываясь на контексте из базы знаний.
- Формируй ответ по одному предложению. В конце каждого предложения ставь разделитель "|".
- Если для полного ответа не хватает информации, задай уточняющий вопрос.
- Если в базе знаний нет ответа, сообщи об этом.
- Используй историю диалога для поддержания контекста.

---
**Контекст из базы знаний:**
{context}
---
"""

class Agent:
    def __init__(self) -> None:
        print("--- Инициализация Агента 'Метротест' (улучшенная версия) ---")
        self.llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.2, streaming=True)
        print("Языковая модель инициализирована.")

        print(f"Подключение к векторной базе в '{PERSIST_DIRECTORY}'...")
        embeddings = OpenAIEmbeddings(chunk_size=1000)
        self.db = Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings)
        self.retriever = self.db.as_retriever(search_type="mmr", search_kwargs={"k": 5})
        print("Подключение к базе данных успешно.")
        
        # 1. Цепочка для переформулирования вопроса с учетом истории
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [("system", contextualize_q_system_prompt), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        history_aware_retriever = create_history_aware_retriever(self.llm, self.retriever, contextualize_q_prompt)

        # 2. Цепочка для генерации финального ответа (без саммаризации)
        qa_prompt = ChatPromptTemplate.from_messages(
            [("system", qa_system_prompt), MessagesPlaceholder("chat_history"), ("human", "{input}")]
        )
        question_answer_chain = create_stuff_documents_chain(self.llm, qa_prompt)

        # 3. Собираем все вместе с помощью create_retrieval_chain
        # Эта функция правильно объединяет ретривер и цепочку ответов
        rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
        
        # 4. Добавляем управление историей диалога
        self.store = {}
        # RunnableWithMessageHistory теперь будет работать корректно,
        # так как create_retrieval_chain возвращает словарь с ключом "answer".
        self.conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )
        print("--- Агент 'Метротест' (улучшенная версия) успешно инициализирован ---")

    def get_session_history(self, session_id: str):
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
        return self.store[session_id]

    def get_response_generator(self, user_question: str, session_id: str):
        stream = self.conversational_rag_chain.stream(
            {"input": user_question},
            config={"configurable": {"session_id": session_id}},
        )
        # От новой цепочки create_retrieval_chain ответ приходит в словаре {'answer': '...'}
        for chunk in stream:
            if 'answer' in chunk:
                yield chunk['answer']
