"""Unit tests for conversational query normalization and provider identity."""

import pytest
from grip import Grip
from google_ai_search.core.engine import _handle_conversational_query, _normalize_ai_answer


def test_conversational_query_greetings_normalization():
    # Test elongated greetings
    for greeting in ["hi", "hii", "hiii", "hey", "heyy", "hello", "helloo", "yo", "sup"]:
        res = _handle_conversational_query(greeting)
        assert res is not None, f"Failed to match greeting '{greeting}'"
        answer, sources, _ = res
        assert "Hello!" in answer
        assert len(sources) == 0

    # Multi-word greetings
    res_there = _handle_conversational_query("hello there")
    assert res_there is not None
    assert "Hello!" in res_there[0]

    res_morning = _handle_conversational_query("good morning")
    assert res_morning is not None
    assert "Good morning!" in res_morning[0]


def test_conversational_identity_across_providers():
    # ChatGPT identity
    res_gpt = _handle_conversational_query("who are you", provider="chatgpt_web")
    assert res_gpt is not None
    assert "ChatGPT" in res_gpt[0]
    assert "OpenAI" in res_gpt[0]

    # Gemini identity
    res_gem = _handle_conversational_query("who are you", provider="gemini_web")
    assert res_gem is not None
    assert "Google Gemini" in res_gem[0]

    # Default / Grip identity
    res_grip = _handle_conversational_query("who are you", provider="google")
    assert res_grip is not None
    assert "Grip AI" in res_grip[0]

    # Typo and repeated character resilience (e.g. whoo aree eyouu, who are youu)
    for q in ["whoo aree eyouu", "who are youu", "who r u", "whoo are you", "who are u"]:
        res = _handle_conversational_query(q, provider="google")
        assert res is not None, f"Failed for query '{q}'"
        assert "Grip AI" in res[0]
        assert "Assistant Overview" not in res[0]
        assert "Core Definition" not in res[0]


def test_conversational_capabilities_and_wellbeing():
    res_how = _handle_conversational_query("how are you")
    assert res_how is not None
    assert "doing well" in res_how[0]

    res_help = _handle_conversational_query("what can you do")
    assert res_help is not None
    assert "assist you with a wide range of tasks" in res_help[0]

    res_thanks = _handle_conversational_query("thank you so much")
    assert res_thanks is not None
    assert "welcome" in res_thanks[0]


def test_client_search_conversational_queries():
    client = Grip()

    # Query with 'hii' on ChatGPT
    res = client.search.query("hii", provider="chatgpt")
    assert "Hello!" in res.answer
    assert "HII | America's Seapower" not in res.answer
    assert "Core Concept" not in res.answer

    # Query with 'who are you' on ChatGPT
    res_who = client.search.query("who are you", provider="chatgpt")
    assert "ChatGPT" in res_who.answer
    assert "OpenAI" in res_who.answer
    assert "Core Concept" not in res_who.answer

    # Streaming query with 'hii'
    chunks = list(client.search.stream("hii", provider="chatgpt"))
    assert len(chunks) > 0
    full_text = "".join(c.delta for c in chunks if c.event == "delta")
    assert "Hello!" in full_text


def test_normalize_ai_answer_strips_robotic_boilerplates():
    raw_robotic = (
        "According to ChatGPT (chatgpt-4o-web):\n\n"
        "Here is a comprehensive analysis of 'Docker':\n\n"
        "Docker is an open-source containerization platform.\n\n"
        "Feel free to ask follow-up questions or explore any of these specific details further."
    )
    normalized = _normalize_ai_answer(raw_robotic, "Docker")
    assert "According to ChatGPT" not in normalized
    assert "Here is a comprehensive analysis" not in normalized
    assert "Feel free to ask follow-up questions" not in normalized
    assert "Docker is an open-source containerization platform." in normalized


def test_technical_explanation_synthesis_chatgpt_style():
    client = Grip()
    res = client.search.query("Explain neural network backpropagation", provider="chatgpt")
    assert "Backpropagation" in res.answer
    assert "### How It Works" in res.answer
    assert "Forward Pass" in res.answer
    assert "Chain Rule" in res.answer
    assert "Core Concept: 'Explain neural network" not in res.answer


def test_coding_solution_synthesis_chatgpt_style():
    client = Grip()
    res_py = client.search.query("how to reverse a string in python", provider="chatgpt")
    assert "[::-1]" in res_py.answer
    assert "```python" in res_py.answer
    assert "Separation of Concerns" not in res_py.answer

    res_js = client.search.query("how to reverse a string in javascript", provider="chatgpt")
    assert "split" in res_js.answer and "reverse" in res_js.answer
    assert "```javascript" in res_js.answer


def test_system_rules_query():
    client = Grip()
    res = client.search.query("system rules", provider="chatgpt")
    assert "behavioral guidelines" in res.answer.lower() or "guidelines" in res.answer.lower()
    assert "Factuality" in res.answer


def test_docker_concept_synthesis():
    client = Grip()
    res = client.search.query("what is docker", provider="chatgpt")
    assert "Docker" in res.answer
    assert "container" in res.answer.lower()
    assert "Core Concept: 'what is docker' focuses on delivering" not in res.answer
