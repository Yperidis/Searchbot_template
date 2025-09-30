import os
import requests

from dotenv import load_dotenv
from edgedb import create_async_client
from fastapi import FastAPI, Query, HTTPException
from gel import ConstraintViolationError
from http import HTTPStatus

from pydantic import BaseModel

from .queries.get_chats_async_edgeql import get_chats as get_chats_query, GetChatsResult
from .queries.get_chat_by_id_async_edgeql import (
    get_chat_by_id as get_chat_by_id_query,
    GetChatByIdResult,
)
from .queries.get_messages_async_edgeql import (
    get_messages as get_messages_query,
    GetMessagesResult,
)
from .queries.create_chat_async_edgeql import (
    create_chat as create_chat_query,
    CreateChatResult,
)
from .queries.add_message_async_edgeql import (
    add_message as add_message_query,
)
from .queries.create_user_async_edgeql import (
    create_user as create_user_query,
    CreateUserResult,
)
from .queries.get_users_async_edgeql import get_users as get_users_query, GetUsersResult
from .queries.get_user_by_name_async_edgeql import (
    get_user_by_name as get_user_by_name_query,
    GetUserByNameResult,
)
from .web import fetch_web_sources, WebSource

_ = load_dotenv()

app = FastAPI()

gel_client = create_async_client()

class SearchTerms(BaseModel):
    query: str

class SearchResult(BaseModel):
    response: str | None = None
    sources: list[WebSource] | None = None


async def search_web(query: str) -> list[WebSource]:
    raw_sources = fetch_web_sources(query, limit=5)
    return [s for s in raw_sources if s.text is not None]


def get_llm_completion(system_prompt: str, messages: list[dict[str, str]]) -> str:
# def get_llm_completion(system_prompt: str, messages: list[dict[str, str]]) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API_TOKEN not found in .env file!")
    
    # The client gets the API key from the environment variable `GEMINI_API_KEY`.
    # client = genai.Client()

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": system_prompt},
                            *messages
                        ]
                    }
                ]
            },
        )
        response.raise_for_status()
        result = response.json()
        if result and 'candidates' in result and result['candidates']:
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            print("No content generated or unexpected response structure.")
            print(result) # Print full response for debugging

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response body: {e.response.text}")


async def generate_answer(
    query: str,
    chat_history: list[GetMessagesResult],
    web_sources: list[WebSource],
) -> SearchResult:
    system_prompt = (
        "You are a helpful assistant that answers user's questions"
        + " by finding relevant information in Hacker News threads."
        + " When answering the question, describe conversations that people have around the subject,"
        + " provided to you as a context, or say i don't know if they are completely irrelevant."
    )

    prompt = f"User search query: {query}\n\nWeb search results:\n"

    for i, source in enumerate(web_sources):
        prompt += f"Result {i} (URL: {source.url}):\n"
        prompt += f"{source.text}\n\n"

    # messages = [{"text": prompt}]
    # messages = [{"role": "user", "content": prompt}]
    messages = [
    {"text": message.body} for message in chat_history
    ]
    messages.append({"text": prompt})

    llm_response = get_llm_completion(
        system_prompt=system_prompt,
        messages=messages,
    )

    search_result = SearchResult(
        response=llm_response,
        sources=web_sources,
    )

    return search_result

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/users")
async def get_users(
    username: str = Query(None),
) -> list[GetUsersResult] | GetUserByNameResult:
    """List all users or get a user by their username"""
    if username:
        user = await get_user_by_name_query(gel_client, name=username)
        if not user:
            raise HTTPException(
                HTTPStatus.NOT_FOUND,
                detail={"error": f"Error: user {username} does not exist."},
            )
        return user
    else:
        return await get_users_query(gel_client)


@app.get("/chats")
async def get_chats(
    username: str = Query(), chat_id: str = Query(None)
) -> list[GetChatsResult] | GetChatByIdResult:
    """List user's chats or get a chat by username and id"""
    if chat_id:
        chat = await get_chat_by_id_query(
            gel_client, username=username, chat_id=chat_id
        )
        if not chat:
            raise HTTPException(
                HTTPStatus.NOT_FOUND,
                detail={"error": f"Chat {chat_id} for user {username} does not exist."},
            )
        return chat
    else:
        return await get_chats_query(gel_client, username=username)


@app.post("/chats", status_code=HTTPStatus.CREATED)
async def post_chat(username: str) -> CreateChatResult:
    return await create_chat_query(gel_client, username=username)



@app.post("/users", status_code=HTTPStatus.CREATED)
async def post_user(username: str = Query()) -> CreateUserResult:
    try:
        return await create_user_query(gel_client, username=username)
    except ConstraintViolationError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={"error": f"Username '{username}' already exists."},
        )


@app.get("/messages")
async def get_messages(
    username: str = Query(), chat_id: str = Query()
) -> list[GetMessagesResult]:
    """Fetch all messages from a chat"""
    return await get_messages_query(gel_client, username=username, chat_id=chat_id)


@app.post("/messages", status_code=HTTPStatus.CREATED)
async def post_messages(
    search_terms: SearchTerms,
    username: str = Query(),
    chat_id: str = Query(),
) -> SearchResult:
    chat_history = await get_messages_query(
        gel_client, username=username, chat_id=chat_id
    )

    _ = await add_message_query(
        gel_client,
        username=username,
        message_role="user",
        message_body=search_terms.query,
        sources=[],
        chat_id=chat_id,
    )

    search_query = search_terms.query
    web_sources = await search_web(search_query)

    search_result = await generate_answer(
        search_terms.query, chat_history, web_sources
    )

    _ = await add_message_query(
        gel_client,
        username=username,
        message_role="assistant",
        message_body=search_result.response,
        sources=search_result.sources,
        chat_id=chat_id,
    )

    return search_result