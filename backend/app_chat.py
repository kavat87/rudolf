import asyncio
import json
import requests
import websockets
import aiohttp
import os
import signal

from tokenizers import Tokenizer
from aiohttp import web


OLLAMA_URL = "http://ollama:11434/api/chat"

MODEL_CONTEXT = {
    "mistral": int(os.getenv("MISTRAL_CTX")),
    "gpt-oss:20b": int(os.getenv("GPTOSS20B_CTX")),
    "gpt-oss:120b": int(os.getenv("GPTOSS120B_CTX")),
    "deepseeker-r1": int(os.getenv("DEEPSEEKERR1_CTX")),
    "saki007ster/CybersecurityRiskAnalyst": int(os.getenv("CYBERRISKANALYST_CTX"))
}

sessions = {}

shutdown_event = asyncio.Event()


def trim_history_by_chars(messages, max_chars=20000):
    total = 0
    i = len(messages) - 1
    r = []

    while i >= 0:
        total += len(messages[i]["content"])
        if total > max_chars:
            print(f"Reached {max_chars} with {total} chars sent")
            break
        else:
            if os.getenv("DEBUG"):
                print("Append to history")
            r.append(messages[i])
            i -= 1

    return list(reversed(r))


def get_prompt_size(messages, model):
    total = 0
    i = len(messages) - 1
    r = ""

    while i >= 0:
        total += len(messages[i]["content"])
        r = f"{r}{messages[i]}\n"
        i -= 1

    tokenizer_json_path = f"/tokenizers/{model.replace('/','_')}/tokenizer.json"
    print(f"Searching tokenizer.json in {tokenizer_json_path}")
    tokenizer = Tokenizer.from_file(tokenizer_json_path)

    safety_margin = 0.05 * MODEL_CONTEXT.get(model, 8192)
    prompt_tokens = len(tokenizer.encode(r.strip()).tokens)
    response_tokens = int(os.getenv("RESPONSE_TOKENS"))

    if prompt_tokens < int(response_tokens * 0.6):
        print(f"prompt tokens < 60% response_tokens {int(response_tokens * 0.6)}")
        prompt_and_response_tokens = int(response_tokens)
    else: 
        print(f"prompt tokens >= 60% response_tokens {int(response_tokens * 0.6)}")
        prompt_and_response_tokens = prompt_tokens + response_tokens

    if prompt_and_response_tokens < int(safety_margin * 0.7):
        print(f"prompt tokens + response tokens < 70% safety_margin {int(safety_margin * 0.7)}")
        full_context = int(safety_margin)
    else:
        print(f"prompt tokens + response tokens >= 70% safety_margin {int(safety_margin * 0.7)}")
        full_context = prompt_and_response_tokens + int(safety_margin)

    return {
        "full_context": full_context,
        "only_context": prompt_tokens
    }


async def stream_ollama(payload, send_chunk, type):
    """
    Funzione comune riusata sia da WS che HTTP
    """
    assistant_text = ""
    thinking_disabled_sent = False
    thinking = payload.get("think", True)

    if type == "ws":
        await send_chunk("___CTX___Asking to model")

    print("Pre request")
    timeout = aiohttp.ClientTimeout(total=None)  
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(OLLAMA_URL, json=payload) as r:

            print("Post request")
            if type == "ws":
                await send_chunk("___CTX___Handling answer")

            first_thinking = True
            first_token = True

            while True:
                line = await r.content.readline()
                if not line:
                    print("no line returned")
                    continue

                chunk = json.loads(line.decode("utf-8"))
                if os.getenv("DEBUG"):
                    print(chunk)

                if chunk.get("done") is True:
                    break 

                if "message" in chunk:
                    if not thinking and not thinking_disabled_sent:
                        thinking_disabled_sent = True
                        print("Thinking has been disabled")
                        if type == "ws":
                            await send_chunk("___THINKING___Thinking has been disabled\n")
                        else:
                            await send_chunk("Thinking has been disabled\n")

                    if "thinking" in chunk["message"]:
                        thinking = chunk["message"]["thinking"]
                        print(f"Thinking: {thinking}")
                        if thinking_disabled_sent == False:
                            if type == "ws":
                                await send_chunk("___THINKING___" + thinking)
                            else:
                                if first_thinking == True:
                                    first_thinking = False
                                    await send_chunk("Thinking:" + thinking)
                                else:
                                    await send_chunk(thinking)
                    else:
                        token = chunk["message"]["content"]
                        print(f"Token: {token}")
                        assistant_text += token
                        if type == "ws":
                            await send_chunk("___TOKEN___" + token)
                        else:
                            if first_token == True:
                                first_token = False
                                await send_chunk("Answer: " + token)
                            else:
                                await send_chunk(token)

                if "error" in chunk:
                    if type == "ws":
                        await send_chunk("___ERROR___" + chunk["error"] + "\n")
                        await send_chunk("___TOKEN___Answer unavailable due to error\n")
                    else:
                        await send_chunk("ERROR: " + chunk["error"] + "\n")

        if type == "ws":
            await send_chunk("___CTX___Flow finished")

    return assistant_text


# =========================
# WEBSOCKET
# =========================
async def ws_handler(websocket):
    sessions[websocket] = []

    try:
        async for message in websocket:

            await websocket.send("___CTX___New message to handle")

            data = json.loads(message)

            sessions[websocket].append({
                "role": "user",
                "content": data["prompt"]
            })

            print("*******************************************")
            context_info = get_prompt_size(sessions[websocket], data["model"])
            print(f"context_info: {context_info}")
            print("*******************************************")

            max_chars = context_info["only_context"] * 4

            sessions[websocket] = trim_history_by_chars(
                sessions[websocket], max_chars
            )

            payload = {
                "model": data["model"],
                "messages": sessions[websocket],
                "stream": True,
                "think": data["thinking"],
                "options": {
                    "num_ctx": context_info["full_context"]
                }
            }

            async def ws_send(chunk):
                await websocket.send(chunk)

            assistant_text = await stream_ollama(payload, ws_send, "ws")

            sessions[websocket].append({
                "role": "assistant",
                "content": assistant_text
            })

            await websocket.send("__END__")

    finally:
        del sessions[websocket]


# =========================
# HTTP STREAMING
# =========================
async def http_chat(request):
    data = await request.json()

    if os.getenv("DEBUG"):
        print(f"data: {data}")

    session_id = id(request)
    sessions[session_id] = []

    sessions[session_id].append({
        "role": "user",
        "content": data["prompt"]
    })

    print("*******************************************")
    context_info = get_prompt_size(sessions[session_id], data["model"])
    print(f"context_info: {context_info}")
    print("*******************************************")

    max_chars = context_info["only_context"] * 4

    if data["history"]:
        max_chars = context * 4
        sessions[session_id] = trim_history_by_chars(
            sessions[session_id], max_chars
        )

    payload = {
        "model": data["model"],
        "messages": sessions[session_id],
        "stream": True,
        "think": data["thinking"],
        "options": {
            "num_ctx": context_info["full_context"] 
        }
    }

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/plain',
            'Transfer-Encoding': 'chunked',
            'Connection': 'keep-alive'
        }
    )

    await response.prepare(request)

    async def http_send(chunk):
        await response.write(chunk.encode("utf-8"))
        await response.drain()

    assistant_text = await stream_ollama(payload, http_send, "api")

    sessions[session_id].append({
        "role": "assistant",
        "content": assistant_text
    })

    await response.write(b"\n")
    await response.drain()
    await response.write_eof()

    del sessions[session_id]
    return response


async def main():
    print("Starting backend")

    def handle_shutdown():
        print("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, handle_shutdown)
    loop.add_signal_handler(signal.SIGINT, handle_shutdown)

    mode = os.getenv("MODE")

    if mode == "http":
        app = web.Application()
        app.router.add_post("/chat", http_chat)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "0.0.0.0", 9765)
        await site.start()

        print("HTTP server started on :9765")

        await shutdown_event.wait()

        print("Stopping HTTP server")
        await runner.cleanup()

    elif mode == "ws":
        ws_server = await websockets.serve(
            ws_handler,
            "0.0.0.0",
            8765,
            ping_interval=20,
            ping_timeout=20,
        )

        print("WebSocket server started on :8765")

        await shutdown_event.wait()

        print("Stopping WebSocket server")
        ws_server.close()
        await ws_server.wait_closed()

    else:
        raise ValueError(f"Unknown MODE: {mode}")

asyncio.run(main())
