"""Unit tests for public web AI providers (ChatGPT, Gemini) and root auto-router."""

from grip import Grip
from grip_engine.providers.chatgpt_web import ChatGPTWebProvider
from grip_engine.providers.gemini_web import GeminiWebProvider
from grip_engine.providers.registry import ProviderRegistry


def test_chatgpt_web_provider_instantiation_and_query():
    provider = ChatGPTWebProvider(name="chatgpt")
    ready, status = provider.ready()
    assert isinstance(ready, bool)
    assert isinstance(status, str)

    res = provider.search("Explain neural network backpropagation")
    assert res.provider == "chatgpt"
    assert "ChatGPT" in res.thinking
    assert len(res.sources) >= 1
    assert "https://chatgpt.com" in res.sources[0].url
    assert len(res.answer) > 20


def test_gemini_web_provider_instantiation_and_query():
    provider = GeminiWebProvider(name="gemini")
    ready, status = provider.ready()
    assert isinstance(ready, bool)
    assert isinstance(status, str)

    res = provider.search("What are gravitational waves?")
    assert res.provider == "gemini"
    assert "Gemini" in res.thinking
    assert len(res.sources) >= 1
    assert "https://gemini.google.com/app" in res.sources[0].url
    assert len(res.answer) > 20


def test_auto_root_router_selection():
    registry = ProviderRegistry()
    registry.register("chatgpt", lambda: ChatGPTWebProvider(name="chatgpt"))
    registry.register("gemini", lambda: GeminiWebProvider(name="gemini"))

    best_prov = registry.get("auto")
    assert best_prov is not None
    assert best_prov.name in ("chatgpt", "gemini", "google")

    best_prov2 = registry.get("best")
    assert best_prov2 is not None


def test_model_and_provider_catalog_listing():
    client = Grip()
    models = client.list_models()
    assert isinstance(models, list)
    assert len(models) >= 3

    model_ids = [m["id"] for m in models]
    assert "google" in model_ids
    assert "chatgpt" in model_ids
    assert "gemini" in model_ids

    providers = client.list_providers()
    assert "google" in providers
    assert "chatgpt" in providers
    assert "gemini" in providers


def test_client_search_with_public_ai_and_auto_providers():
    client = Grip()

    # Query using chatgpt provider
    res_chatgpt = client.search.query("Hello ChatGPT", provider="chatgpt")
    assert res_chatgpt.provider in ("chatgpt", "chatgpt_web")
    assert len(res_chatgpt.answer) > 0

    # Query using gemini provider
    res_gemini = client.search.query("Hello Gemini", provider="gemini")
    assert res_gemini.provider in ("gemini", "gemini_web")
    assert len(res_gemini.answer) > 0

    # Query using auto root router
    res_auto = client.search.query("Auto routed query", provider="auto")
    assert res_auto.provider is not None
    assert len(res_auto.answer) > 0


def test_agent_with_public_web_providers():
    client = Grip()

    agent_gpt = client.create_agent(
        name="GPTWebAgent",
        provider="chatgpt",
    )
    assert agent_gpt.provider == "chatgpt"
    assert agent_gpt.model == "chatgpt-4o-web"

    agent_gemini = client.create_agent(
        name="GeminiWebAgent",
        provider="gemini",
    )
    assert agent_gemini.provider == "gemini"
    assert agent_gemini.model == "gemini-web"
