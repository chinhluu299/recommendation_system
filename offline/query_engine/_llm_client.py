from __future__ import annotations

import os
import time
import re
from openai import OpenAI


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.5-flash"

_MAX_RETRIES = 5
_BASE_WAIT = 15
_MAX_WAIT = 120
_MAX_CONTINUES = 3


def _load_api_key() -> str:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path)
    except ImportError:
        if os.path.isfile(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())
    
    random_keys = [f"GEMINI_API_KEY_{i}" for i in range(1, 6)]
    key = next((os.environ.get(k) for k in random_keys if os.environ.get(k)), "")
    if not key:
        raise EnvironmentError(
            "Thiếu GEMINI_API_KEY.\n"
            "Đặt biến môi trường: export GEMINI_API_KEY='your-key'\n"
            "Hoặc tạo file ver2/.env với dòng: GEMINI_API_KEY=your-key"
        )
    return key


_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=GEMINI_BASE_URL,
            api_key=_load_api_key(),
        )
    return _client


def get_model() -> str:
    return GEMINI_MODEL


def _extract_text(resp) -> str:
    content = resp.choices[0].message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(text)
        return "".join(parts)
    return str(content or "")


def _create_completion(client: OpenAI, model: str, messages: list[dict], max_tokens: int, temperature: float):
    base = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    payloads = [
        {**base, "max_completion_tokens": max_tokens},
        {**base, "max_tokens": max_tokens},
        {**base, "max_tokens": max_tokens, "extra_body": {"max_output_tokens": max_tokens}},
    ]

    last_type_error = None
    for payload in payloads:
        try:
            return client.chat.completions.create(**payload)
        except TypeError as e:
            last_type_error = e
            continue
        except Exception:
            raise

    if last_type_error is not None:
        raise last_type_error
    raise RuntimeError("Không thể gọi chat completion.")


def _request_with_retry(client: OpenAI, model: str, messages: list[dict], max_tokens: int, temperature: float):
    for attempt in range(_MAX_RETRIES):
        try:
            return _create_completion(
                client=client,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            err_str = str(e)
            is_429  = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str

            if not is_429 or attempt == _MAX_RETRIES - 1:
                raise

            wait = _BASE_WAIT * (2 ** attempt)
            m = re.search(r"retry[_\s]in[_\s]([\d.]+)s", err_str, re.IGNORECASE)
            if m:
                wait = float(m.group(1)) + 2

            wait = min(wait, _MAX_WAIT)
            print(f"  [429] Rate limit — chờ {wait:.0f}s rồi thử lại "
                  f"(lần {attempt + 1}/{_MAX_RETRIES}) ...")
            time.sleep(wait)

    raise RuntimeError("Vẫn lỗi 429 sau tất cả các lần retry.")


def chat(messages: list[dict], max_tokens: int = 2048, temperature: float = 0.1) -> str:
    client = get_client()
    model  = get_model()

    resp = _request_with_retry(
        client=client,
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    full_text = _extract_text(resp)
    finish_reason = getattr(resp.choices[0], "finish_reason", None)

    continue_count = 0
    while finish_reason == "length" and continue_count < _MAX_CONTINUES:
        continue_count += 1
        cont_messages = list(messages) + [
            {"role": "assistant", "content": full_text},
            {
                "role": "user",
                "content": "Tiếp tục đúng từ chỗ đang dở, không lặp lại nội dung đã trả lời.",
            },
        ]
        cont_resp = _request_with_retry(
            client=client,
            model=model,
            messages=cont_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        cont_text = _extract_text(cont_resp)
        if cont_text:
            if full_text and not full_text.endswith(("\n", " ")):
                full_text += " "
            full_text += cont_text
        finish_reason = getattr(cont_resp.choices[0], "finish_reason", None)

    return full_text or ""
