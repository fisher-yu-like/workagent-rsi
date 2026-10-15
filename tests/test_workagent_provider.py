from pathlib import Path

from workagent_rsi.workagent_provider import CodexOfficeProvider, WorkAgentConfig


def test_codex_cli_provider_command_uses_configured_remote_model(tmp_path: Path):
    provider = CodexOfficeProvider(WorkAgentConfig(model="gpt-5.4", backend="codex-cli"))

    command = provider.command(tmp_path, tmp_path / "response.json", tmp_path / "schema.json")

    assert command[:3] == ["codex", "exec", "--ignore-user-config"]
    assert command[command.index("--model") + 1] == "gpt-5.4"
    assert "--oss" not in command
    assert "--local-provider" not in command


def test_codex_cli_provider_identity_is_not_labeled_as_ollama():
    provider = CodexOfficeProvider(WorkAgentConfig(model="gpt-5.4", backend="codex-cli"))

    assert provider.model_identity == "codex-cli:gpt-5.4"


def test_openai_chat_provider_uses_explicit_api_model_identity():
    provider = CodexOfficeProvider(
        WorkAgentConfig(
            model="claude-haiku-4-5-20251001",
            backend="openai-chat",
            api_base_url="https://api.example.test/v1",
        )
    )

    assert provider.model_identity == "openai-chat:claude-haiku-4-5-20251001"


def test_openai_chat_retry_configuration_is_bounded():
    config = WorkAgentConfig(backend="openai-chat", api_max_retries=4, api_retry_delay_seconds=1.5)

    assert config.api_max_retries == 4
    assert config.api_retry_delay_seconds == 1.5
