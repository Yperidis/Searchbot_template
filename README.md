# Introduction

This project aims at establishing a generic [RAG](https://proceedings.neurips.cc/paper/2020/file/6b493230205f780e1bc26945df7481e5-Paper.pdf) (retrieval augmented generator) for the fast prototyping of a domain-focused conversational bot. The database system on which the approach is based is that of [gel](https://www.geldata.com/). In fact, the whole endeavour is expanding on a [tutorial](https://docs.geldata.com/learn/tutorials/ai_fastapi_searchbot) of gel's documentation on building a search bot with memory.

# Setup

## Environments and Dependency Management
For creating virtual environments and dependency management, following the gel tutorial, we use [Astral's](https://astral.sh/) [uv](https://docs.astral.sh/uv/).

## LLM Backend
We employ Google's Gemini 2.5 free tier from the [provided API](https://ai.google.dev/gemini-api/docs) for experimentation with the standard python *requests* package. Customisation of the `GEMINI_API_KEY` is naturally required.