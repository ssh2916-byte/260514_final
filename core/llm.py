import streamlit as st
from openai import OpenAI


def _stream_generator(response):
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def call_llm(prompt: str, system: str, stream: bool = False):
    client = OpenAI(api_key=st.session_state["openai_api_key"])
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        stream=stream,
    )
    if stream:
        return _stream_generator(response)
    return response.choices[0].message.content
