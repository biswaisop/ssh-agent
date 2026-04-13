from langchain_groq import ChatGroq
from config import settings

llm = ChatGroq(
    model=settings.MODEL,
    temperature=settings.TEMPERATURE, 
    api_key=settings.GROQ
)