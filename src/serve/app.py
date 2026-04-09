from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
from fastapi import FastAPI, HTTPException
from peft import PeftModel
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer


def _env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


BASE_MODEL = _env("BASE_MODEL", "facebook/opt-2.7b")
LATEST_OK_POINTER = _env(
    "LATEST_OK_POINTER", "/workspace/data/runs/LATEST_OK_ADAPTER_ID"
)
SERVE_HOST = _env("SERVE_HOST", "0.0.0.0")
SERVE_PORT = int(_env("SERVE_PORT", "8901"))
HEALTH_PATH = _env("HEALTH_PATH", "/health")


@dataclass
class LoadedModelState:
    base_model: str
    pointer_path: Path
    adapter_run_id: Optional[str]
    adapter_path: Optional[Path]
    runtime_device: str
    loaded_at_unix: float
    model: Any
    tokenizer: Any


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    temperature: float = 0.0
    max_tokens: int = 256


class ChatCompletionChoiceMessage(BaseModel):
    role: str
    content: str


class ChatCompletionChoice(BaseModel):
    index: int
    finish_reason: str
    message: ChatCompletionChoiceMessage


class UsageBlock(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: UsageBlock


class ReloadResponse(BaseModel):
    status: str
    adapter_run_id: Optional[str]
    adapter_path: Optional[str]
    runtime_device: str


app = FastAPI(title="llm-homelab-serving", version="0.1.0")

_state: Optional[LoadedModelState] = None


def resolve_torch_dtype() -> Optional[torch.dtype]:
    if torch.cuda.is_available():
        return torch.float16
    return None


def build_prompt(messages: List[ChatMessage]) -> str:
    if not messages:
        raise ValueError("messages must contain at least one item")

    system_parts: List[str] = []
    conversation_parts: List[str] = []

    for msg in messages:
        role = (msg.role or "").strip().lower()
        content = (msg.content or "").strip()
        if not content:
            continue

        if role == "system":
            system_parts.append(content)
        elif role == "user":
            conversation_parts.append(f"### Instruction:\n{content}")
        elif role == "assistant":
            conversation_parts.append(f"### Assistant:\n{content}")
        else:
            conversation_parts.append(f"### {role.title() or 'User'}:\n{content}")

    if not conversation_parts and not system_parts:
        raise ValueError("messages must contain non-empty content")

    sections: List[str] = []
    if system_parts:
        sections.append("### System:\n" + "\n\n".join(system_parts))
    sections.extend(conversation_parts)
    sections.append("### Response:\n")
    return "\n\n".join(sections)


def resolve_adapter_run_id(pointer_path: Path) -> str:
    if not pointer_path.exists():
        raise FileNotFoundError(f"Pointer file not found: {pointer_path}")

    run_id = pointer_path.read_text(encoding="utf-8").strip()
    if not run_id:
        raise ValueError(f"Pointer file is empty: {pointer_path}")
    return run_id


def resolve_adapter_path(pointer_path: Path) -> Tuple[str, Path]:
    run_id = resolve_adapter_run_id(pointer_path)
    adapter_path = Path("/workspace/data/models") / run_id
    if not adapter_path.exists():
        raise FileNotFoundError(f"Adapter directory not found: {adapter_path}")
    if not (adapter_path / "adapter_config.json").exists():
        raise FileNotFoundError(
            f"adapter_config.json missing for promoted adapter: {adapter_path}"
        )
    return run_id, adapter_path


def load_model_state() -> LoadedModelState:
    pointer_path = Path(LATEST_OK_POINTER)
    adapter_run_id, adapter_path = resolve_adapter_path(pointer_path)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    torch_dtype = resolve_torch_dtype()
    device_map = "auto" if torch.cuda.is_available() else None

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch_dtype,
        device_map=device_map,
    )
    model = PeftModel.from_pretrained(model, str(adapter_path))
    model.eval()

    runtime_device = "cpu"
    if hasattr(model, "device"):
        runtime_device = str(model.device)

    return LoadedModelState(
        base_model=BASE_MODEL,
        pointer_path=pointer_path,
        adapter_run_id=adapter_run_id,
        adapter_path=adapter_path,
        runtime_device=runtime_device,
        loaded_at_unix=time.time(),
        model=model,
        tokenizer=tokenizer,
    )


def get_state() -> LoadedModelState:
    global _state
    if _state is None:
        _state = load_model_state()
    return _state


@torch.no_grad()
def generate_text(
    state: LoadedModelState,
    prompt: str,
    max_tokens: int,
    temperature: float,
) -> Tuple[str, UsageBlock]:
    tokenizer = state.tokenizer
    model = state.model

    inputs = tokenizer(prompt, return_tensors="pt")
    if hasattr(model, "device"):
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

    do_sample = temperature > 0.0
    gen_kwargs: Dict[str, Any] = {
        "max_new_tokens": max(1, int(max_tokens)),
        "do_sample": do_sample,
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
    }
    if do_sample:
        gen_kwargs["temperature"] = max(float(temperature), 1e-6)
        gen_kwargs["top_p"] = 1.0

    outputs = model.generate(
        input_ids=inputs["input_ids"],
        attention_mask=inputs.get("attention_mask"),
        **gen_kwargs,
    )

    prompt_len = int(inputs["input_ids"].shape[1])
    completion_ids = outputs[0][prompt_len:]
    completion_text = tokenizer.decode(completion_ids, skip_special_tokens=True).strip()

    prompt_tokens = int(inputs["input_ids"].shape[1])
    completion_tokens = int(completion_ids.shape[0])
    usage = UsageBlock(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return completion_text, usage


@app.on_event("startup")
def startup_event() -> None:
    global _state
    _state = load_model_state()


@app.get(HEALTH_PATH)
def health() -> Dict[str, Any]:
    try:
        state = get_state()
        return {
            "status": "ok",
            "service": "serve",
            "base_model": state.base_model,
            "adapter_run_id": state.adapter_run_id,
            "adapter_path": str(state.adapter_path) if state.adapter_path else None,
            "pointer_path": str(state.pointer_path),
            "runtime_device": state.runtime_device,
            "loaded_at_unix": state.loaded_at_unix,
            "serve_host": SERVE_HOST,
            "serve_port": SERVE_PORT,
        }
    except Exception as exc:
        return {
            "status": "error",
            "service": "serve",
            "error": str(exc),
            "pointer_path": LATEST_OK_POINTER,
            "base_model": BASE_MODEL,
        }


@app.post("/reload", response_model=ReloadResponse)
def reload_model() -> ReloadResponse:
    global _state
    try:
        _state = load_model_state()
        return ReloadResponse(
            status="ok",
            adapter_run_id=_state.adapter_run_id,
            adapter_path=str(_state.adapter_path) if _state.adapter_path else None,
            runtime_device=_state.runtime_device,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reload failed: {exc}") from exc


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
def chat_completions(req: ChatCompletionRequest) -> ChatCompletionResponse:
    try:
        state = get_state()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Model not ready: {exc}") from exc

    try:
        prompt = build_prompt(req.messages)
        text, usage = generate_text(
            state=state,
            prompt=prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Generation failed: {exc}"
        ) from exc

    model_name = req.model or state.adapter_run_id or state.base_model
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        object="chat.completion",
        created=int(time.time()),
        model=model_name,
        choices=[
            ChatCompletionChoice(
                index=0,
                finish_reason="stop",
                message=ChatCompletionChoiceMessage(role="assistant", content=text),
            )
        ],
        usage=usage,
    )
