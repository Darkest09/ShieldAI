from app.proxy.upstream_client import chat_completions_endpoint


def test_chat_endpoint_openai_host_only() -> None:
    assert (
        chat_completions_endpoint("https://api.openai.com")
        == "https://api.openai.com/v1/chat/completions"
    )


def test_chat_endpoint_openai_with_v1() -> None:
    assert (
        chat_completions_endpoint("https://api.openai.com/v1")
        == "https://api.openai.com/v1/chat/completions"
    )


def test_chat_endpoint_groq() -> None:
    assert (
        chat_completions_endpoint("https://api.groq.com/openai/v1")
        == "https://api.groq.com/openai/v1/chat/completions"
    )
