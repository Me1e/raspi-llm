#!/usr/bin/env python3

import asyncio
import websockets
import logging
import json
import base64 # 오디오 데이터 Base64 인코딩용

# 기본 로깅 설정
logging.basicConfig(level=logging.INFO)
logging.info(f"Using websockets library version: {websockets.__version__}")

# --- Gemini API 설정 ---
GEMINI_API_KEY = "YOUR_API_KEY_HERE" # 실제 API 키로 교체!
GEMINI_MODEL_NAME = "gemini-2.0-flash-live-001"
GEMINI_WS_URL_BASE = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
# -------------------------

# 웹 클라이언트와 Gemini 간 메시지 전달을 위한 큐
web_text_to_gemini_queue = asyncio.Queue() # 텍스트 메시지용
gemini_to_web_queue = asyncio.Queue()

connected_web_clients = set()

# Gemini WebSocket 연결을 저장할 변수
gemini_websocket_connection = None


async def gemini_processor():
    global gemini_websocket_connection
    if GEMINI_API_KEY == "YOUR_API_KEY_HERE":
        logging.error("Gemini API Key is not set. Please update GEMINI_API_KEY in main.py.")
        await gemini_to_web_queue.put("Error: Gemini API Key not configured on the server.")
        return

    uri_with_key = f"{GEMINI_WS_URL_BASE}?key={GEMINI_API_KEY}"
    
    while True: # 재연결 로직 추가
        try:
            async with websockets.connect(uri_with_key) as gemini_ws:
                gemini_websocket_connection = gemini_ws # 연결 저장
                logging.info("Successfully connected to Gemini Live API.")

                setup_message = {
                    "setup": {
                        "model": f"models/{GEMINI_MODEL_NAME}",
                        "generationConfig": {
                            "responseModalities": ["TEXT"] # 아직 텍스트 응답
                        },
                        "systemInstruction": {
                            "parts": [{"text": "You are a friendly and helpful Raspberry Pi assistant."}]
                        }
                    }
                }
                await gemini_ws.send(json.dumps(setup_message))
                logging.info(f"Sent Gemini setup message: {json.dumps(setup_message)}")

                response_raw = await gemini_ws.recv()
                response_data = json.loads(response_raw)
                logging.info(f"Received initial response from Gemini: {response_data}")

                if "setupComplete" not in response_data:
                    error_msg = f"Gemini setup failed: {response_data}"
                    logging.error(error_msg)
                    await gemini_to_web_queue.put(f"Error: {error_msg}")
                    gemini_websocket_connection = None # 연결 실패 시 초기화
                    await asyncio.sleep(5) # 재시도 전 대기
                    continue # 재연결 시도

                logging.info("Gemini session setup complete.")
                await gemini_to_web_queue.put("[Gemini session ready]")

                async def forward_text_to_gemini():
                    while True:
                        if not gemini_websocket_connection: break
                        try:
                            message_from_web = await web_text_to_gemini_queue.get()
                            if gemini_websocket_connection and gemini_websocket_connection.open:
                                logging.info(f"Relaying TEXT from web client to Gemini: {message_from_web}")
                                gemini_client_content = {
                                    "clientContent": {
                                        "turns": [{"role": "user", "parts": [{"text": str(message_from_web)}]}],
                                        "turnComplete": True
                                    }
                                }
                                await gemini_websocket_connection.send(json.dumps(gemini_client_content))
                            else:
                                logging.warning("Gemini connection closed. Cannot send text.")
                                web_text_to_gemini_queue.put_nowait(message_from_web) # 메시지 다시 큐에 넣기 (선택적)
                                break
                        except websockets.exceptions.ConnectionClosed:
                            logging.warning("Connection to Gemini closed (forward_text_to_gemini).")
                            web_text_to_gemini_queue.put_nowait(message_from_web) # 메시지 다시 큐에 넣기
                            break
                        except Exception as e_fwd:
                            logging.error(f"Error in forward_text_to_gemini: {e_fwd}")
                        finally:
                             if 'message_from_web' in locals(): # task_done 호출 보장
                                web_text_to_gemini_queue.task_done()


                async def receive_from_gemini():
                    while True:
                        if not gemini_websocket_connection: break
                        try:
                            message_from_gemini_raw = await gemini_websocket_connection.recv()
                            logging.info(f"Received from Gemini: {message_from_gemini_raw[:500]}") # 너무 길면 잘라서 로깅
                            message_data = json.loads(message_from_gemini_raw)
                            # (이전과 동일한 텍스트 처리 로직)
                            text_response_to_web = ""
                            if "serverContent" in message_data:
                                server_content = message_data["serverContent"]
                                if "modelTurn" in server_content and server_content["modelTurn"].get("parts"):
                                    for part in server_content["modelTurn"]["parts"]:
                                        if "text" in part:
                                            text_response_to_web += part["text"] + " "
                                elif "interrupted" in server_content and server_content["interrupted"]:
                                    text_response_to_web = "[Gemini: Interrupted]"
                                elif "turnComplete" in server_content and server_content["turnComplete"]:
                                    if not text_response_to_web:
                                        text_response_to_web = "[Gemini: Turn complete]"
                            # ... (기타 메시지 타입 처리) ...
                            elif "toolCall" in message_data: # 이후 단계에서 처리
                                text_response_to_web = f"[Gemini Tool Call (not yet handled)]"
                            elif "goAway" in message_data:
                                logging.warning(f"Gemini server sent GoAway: {message_data['goAway']}")
                                text_response_to_web = "[Gemini session ending]"
                                break # goAway 받으면 루프 종료 및 재연결 유도
                            else:
                                text_response_to_web = f"[Gemini: Unhandled message]"


                            if text_response_to_web.strip():
                                await gemini_to_web_queue.put(text_response_to_web.strip())

                        except websockets.exceptions.ConnectionClosed:
                            logging.warning("Connection to Gemini closed (receive_from_gemini).")
                            break # 루프 종료 및 재연결 유도
                        except json.JSONDecodeError:
                            logging.error(f"Failed to decode JSON from Gemini: {message_from_gemini_raw[:500]}")
                        except Exception as e_recv:
                            logging.error(f"Error in receive_from_gemini: {e_recv}")
                
                await asyncio.gather(
                    forward_text_to_gemini(),
                    receive_from_gemini()
                )

        except (websockets.exceptions.WebSocketException, ConnectionRefusedError, OSError) as e:
            logging.error(f"Gemini connection/setup error: {e}. Retrying in 5 seconds...")
        except Exception as e_outer:
            logging.error(f"Unexpected error in gemini_processor outer loop: {e_outer}. Retrying in 5 seconds...")
        finally:
            gemini_websocket_connection = None # 연결 종료 시 초기화
            logging.info("Gemini processor attempting to reconnect or has finished a cycle.")
            await gemini_to_web_queue.put("[Error: Disconnected from Gemini. Attempting to reconnect...]")
            await asyncio.sleep(5) # 재연결 시도 전 대기


async def rpi_websocket_handler(websocket, path=None):
    global gemini_websocket_connection
    logging.info(f"Web client connected: {websocket.remote_address}")
    connected_web_clients.add(websocket)
    try:
        async for message_from_web in websocket:
            if isinstance(message_from_web, str): # 텍스트 메시지 처리
                logging.info(f"Received TEXT from web client {websocket.remote_address}: {message_from_web}")
                await web_text_to_gemini_queue.put(message_from_web)
            elif isinstance(message_from_web, bytes): # 바이너리 (오디오) 메시지 처리
                logging.info(f"Received AUDIO ({len(message_from_web)} bytes) from web client {websocket.remote_address}")
                if gemini_websocket_connection and gemini_websocket_connection.open:
                    try:
                        audio_base64 = base64.b64encode(message_from_web).decode('utf-8')
                        gemini_realtime_input = {
                            "realtimeInput": {
                                "audio": {"data": audio_base64, "mimeType": "audio/pcm;rate=16000"}
                                # 클라이언트가 16kHz Float32 ArrayBuffer를 보내고, 여기서 Base64 인코딩.
                                # Gemini는 rate=16000 정보를 바탕으로 처리 시도.
                            }
                        }
                        await gemini_websocket_connection.send(json.dumps(gemini_realtime_input))
                        logging.info("Sent audio chunk to Gemini.")
                    except websockets.exceptions.ConnectionClosed:
                        logging.warning("Gemini connection closed. Cannot send audio.")
                        # 오디오 데이터는 유실될 수 있음 (큐에 다시 넣지 않음)
                    except Exception as e_audio_send:
                        logging.error(f"Error sending audio to Gemini: {e_audio_send}")
                else:
                    logging.warning("Gemini not connected. Cannot send audio.")
            else:
                logging.warning(f"Received unknown message type from {websocket.remote_address}")

    except websockets.exceptions.ConnectionClosedOK:
        logging.info(f"Web client {websocket.remote_address} disconnected normally.")
    # ... (기존의 다른 예외 처리) ...
    except Exception as e:
        logging.error(f"An error with web client {websocket.remote_address}: {e}")
    finally:
        logging.info(f"Web client connection handler for {websocket.remote_address} finished.")
        connected_web_clients.remove(websocket)


async def broadcast_gemini_responses():
    while True:
        message_to_broadcast = await gemini_to_web_queue.get()
        # ... (이전과 동일한 브로드캐스트 로직) ...
        active_clients = list(connected_web_clients) # 반복 중 변경 방지
        if active_clients:
            results = await asyncio.gather(
                *[client_ws.send(str(message_to_broadcast)) for client_ws in active_clients],
                return_exceptions=True
            )
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"Error sending to client {active_clients[i].remote_address}: {result}")
                    # 필요시 여기서 해당 클라이언트 연결 종료 또는 제거
        gemini_to_web_queue.task_done()


async def start_main_server():
    # ... (이전과 동일) ...
    server_host = "0.0.0.0"
    server_port = 8765
    logging.info(f"Starting RPi WebSocket server on ws://{server_host}:{server_port}")

    asyncio.create_task(gemini_processor())
    asyncio.create_task(broadcast_gemini_responses())

    async with websockets.serve(rpi_websocket_handler, server_host, server_port):
        await asyncio.Future()

if __name__ == "__main__":
    # ... (이전과 동일) ...
    try:
        asyncio.run(start_main_server())
    except KeyboardInterrupt:
        logging.info("Main server shutting down.")
    except Exception as e:
        logging.error(f"Failed to start main server: {e}")