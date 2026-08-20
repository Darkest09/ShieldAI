import pytest

from app.core.vault import DictVault


@pytest.mark.asyncio
async def test_deanonymize_roundtrip_known_token() -> None:
    from app.proxy.postflight import deanonymize_text

    vault = DictVault(ttl_seconds=60)
    vk = "req-1"
    token = "[SHIELD_p_00001]"
    await vault.put(vk, token, "nepali-secret", "X")
    out = await deanonymize_text(f"hey {token}!", vault=vault, vault_key=vk)
    assert out == "hey nepali-secret!"

