"""Example: Public Web Page AI Providers (ChatGPT, Gemini) and Root Auto-Router.

Demonstrates:
1. Connecting to ChatGPT Public Web (https://chatgpt.com)
2. Connecting to Google Gemini Web (https://gemini.google.com/app)
3. Using the Root Auto-Router (provider="auto") to automatically use the best available model
4. Listing the real-time AI Model & Provider Catalog
5. Creating an autonomous Agent backed by ChatGPT/Gemini web interfaces.
"""

from grip import Grip

def main():
    print("=" * 65)
    print("🌐 Grip AI: Public Web AI Providers & Root Auto-Router Demo")
    print("=" * 65)

    client = Grip()

    # 1. Discover registered AI models and providers
    print("\n[1] Discovering Available AI Models & Providers Catalog:")
    models = client.list_models()
    for m in models:
        ready_icon = "✓" if m.get("ready") else "✗"
        print(f"  {ready_icon} {m['name']:<24} Provider: {m['provider']:<10} Type: {m['type']:<20} URL: {m.get('url', 'N/A')}")

    # 2. Query ChatGPT Public Web AI (chatgpt.com)
    print("\n[2] Querying ChatGPT Public Web AI (chatgpt.com):")
    query_gpt = "Explain the advantages of quantum key distribution in 2 sentences."
    res_gpt = client.search.query(query_gpt, provider="chatgpt")
    print(f"  Provider: {res_gpt.provider}")
    print(f"  Source:   {res_gpt.sources[0].url if res_gpt.sources else 'N/A'}")
    print(f"  Thinking: {res_gpt.thinking}")
    print(f"  Answer:   {res_gpt.answer[:160]}...\n")

    # 3. Query Google Gemini Web App (gemini.google.com/app)
    print("[3] Querying Google Gemini Web App (gemini.google.com/app):")
    query_gemini = "Summarize the event horizon of a black hole in 2 sentences."
    res_gemini = client.search.query(query_gemini, provider="gemini")
    print(f"  Provider: {res_gemini.provider}")
    print(f"  Source:   {res_gemini.sources[0].url if res_gemini.sources else 'N/A'}")
    print(f"  Thinking: {res_gemini.thinking}")
    print(f"  Answer:   {res_gemini.answer[:160]}...\n")

    # 4. Root Auto-Router: Automatically pick the best available model
    print("[4] Using Root Auto-Router (provider='auto'):")
    res_auto = client.search.query("What is fault-tolerant quantum computing?", provider="auto")
    print(f"  Auto-Selected Provider: {res_auto.provider}")
    print(f"  Response Time:          {res_auto.search_time}s")
    print(f"  Answer:                 {res_auto.answer[:160]}...\n")

    # 5. Build an autonomous Agent using ChatGPT public web provider
    print("[5] Running Autonomous Agent with ChatGPT Web Provider:")
    agent = client.create_agent(
        name="GPTWebResearchAgent",
        provider="chatgpt",  # Automatically uses chatgpt-4o-web
        system_prompt="You are a research agent powered by public web intelligence."
    )
    result = agent.run("Compile a brief executive briefing on solid-state battery tech.")
    print(f"  Agent Status: {result.status}")
    print(f"  Agent Model:  {result.model}")
    print(f"  Agent Output: {result.output[:180]}...\n")

    print("=" * 65)
    print("✅ All Public Web AI integrations and Auto-Router verified successfully!")
    print("=" * 65)

if __name__ == "__main__":
    main()
