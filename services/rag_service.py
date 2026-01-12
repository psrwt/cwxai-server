import time
import traceback
import os


from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage


from utils.document_processing import initialize_retriever
from langchain_openai import AzureChatOpenAI    
from config.settings import Config
from dotenv import load_dotenv

load_dotenv()

class RAGService:
    def __init__(self, user_id: str, file_path: str):
        """
        Initializes the RAG service for a given user and blob file.
        """
        self.chain = None  # Ensure attribute exists even if initialization fails.
        try:
            print(f"Initializing retriever for user {user_id} using file {file_path}...")
            self.retriever = initialize_retriever(user_id, file_path)
            print("Initializing Azure OpenAI model...")
            self.model = AzureChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=800,
                timeout=120,
                api_version="2024-08-01-preview",
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                openai_api_key=os.getenv("AZURE_OPENAI_API_KEY")
            )
            if not os.getenv("AZURE_OPENAI_API_KEY"):
                raise ValueError("AZURE_OPENAI_API_KEY is missing or invalid!")
            if not os.getenv("AZURE_OPENAI_ENDPOINT"):
                raise ValueError("AZURE_OPENAI_ENDPOINT is missing or invalid!")
            print("Creating retrieval chain...")
            self.chain = self._create_chain()
            print("Initialization complete for user!")
        except Exception as e:
            print("Error during initialization:")
            traceback.print_exc()

    def _create_chain(self):
        """
        Creates the retrieval-augmented generation (RAG) chain.
        """
        try:
            print("Setting up contextual question prompt...")
            contextualize_q_prompt = ChatPromptTemplate.from_messages([
                ("system", "Given a chat history and latest question, reformulate it as a standalone question."),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
            ])
            print("Creating history-aware retriever...")
            history_aware_retriever = create_history_aware_retriever(
                self.model, self.retriever, contextualize_q_prompt
            )
            print("Setting up QA prompt...")
            qa_prompt = ChatPromptTemplate.from_messages([
                ("system",
 "You are a former Senior Partner at a leading global strategy firm with over 20 years advising CEOs and private‑equity boards. "
 "You deliver board‑level strategy in simple, actionable terms anyone can follow.\n\n"
 "Your answers should be:\n"
 " • Strategic: focused on long‑term growth and competitive advantage.\n"
 " • Practical: broken into clear steps, with owners, timelines, and KPIs.\n"
 " • Precise: based on facts, financials, and proven frameworks.\n"
 " • Executive‑ready: concise, high‑impact, and tailored for decision‑makers.\n\n"
 "How to answer:\n"
 "1. Use only the context you’re given.\n"
 "2. Explain ideas in plain language—avoid jargon.\n"
 "3. Whenever you can, include numbers (ROI, cost savings, revenue gains).\n"
 "4. Cite any sources or report titles you used.\n"
 "5. If you’re not sure, start with ‘Based on available information…’\n\n"
 "6. If the question is not related to the context, say: ‘I can’t help with that.’\n\n"
 "7. The output should be a valid markdown without ```’\n\n"
 "Context:\n{context}"),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", "{input}"),
            ])
            print("Creating question-answering chain...")
            question_answer_chain = create_stuff_documents_chain(self.model, qa_prompt)
            print("Retrieval chain successfully created!")
            return create_retrieval_chain(history_aware_retriever, question_answer_chain)
        except Exception as e:
            print("Error in _create_chain:")
            traceback.print_exc()
            return None

    def generate_response(self, query, chat_history=None, use_chat_history=True):
        """
        Generates a response using the RAG chain.
        """
        try:
            print("\n--- Generating Response ---")
            if not isinstance(query, str):
                print("Error: Query must be a string.")
                return "Invalid query format."
            if use_chat_history and chat_history is not None and not isinstance(chat_history, list):
                print("Error: Chat history must be a list.")
                return "Invalid chat history format."
            
            input_data = {"input": query}
            if use_chat_history:
                input_data["chat_history"] = chat_history
            
            try:
                response = self.chain.invoke(input_data)
            except Exception as e:
                print("Error in self.chain.invoke():")
                traceback.print_exc()
                return "Error invoking retrieval chain."
            
            answer = response.get("answer", "I couldn't find an answer.")
            retrieved_docs = response.get("context", [])
            
            urls = set()
            for doc in retrieved_docs:
                url = doc.metadata.get("url", "")
                if url:
                    urls.add(url)
            
            citations = ""
            if urls:
                citations = "\n\n**Sources:**\n" + "\n".join(f"- {url}" for url in urls)
            
            full_response = f"{answer}{citations}"
            return full_response
        except Exception as e:
            print("General error in generate_response:")
            traceback.print_exc()
            return "Error generating response."
