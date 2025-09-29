import os
import requests

from dotenv import load_dotenv
from edgedb import create_async_client
from fastapi import FastAPI, Query, HTTPException
from gel import ConstraintViolationError
from http import HTTPStatus

from pydantic import BaseModel

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

    messages = [{"text": prompt}]

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


@app.post("/users", status_code=HTTPStatus.CREATED)
async def post_user(username: str = Query()) -> CreateUserResult:
    try:
        return await create_user_query(gel_client, username=username)
    except ConstraintViolationError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail={"error": f"Username '{username}' already exists."},
        )


@app.post("/search")
async def search(search_terms: SearchTerms) -> SearchResult:
    web_sources = await search_web(search_terms.query)
    search_result = await generate_answer(search_terms.query, web_sources)
    return search_result
    # return SearchResult(
    #     response=search_terms.query, sources=web_sources
    # )