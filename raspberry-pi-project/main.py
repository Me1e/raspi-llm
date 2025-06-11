#!/usr/bin/env python3

import asyncio
import websockets
import logging
import json
import base64 # 오디오 데이터 Base64 인코딩용
from websockets.connection import State # State 임포트 추가
from picamera2 import Picamera2 # picamera2 임포트
import io # 이미지 스트림 처리를 위해
import time # 프레임 간격 제어를 위해

# 기본 로깅 설정
logging.basicConfig(level=logging.INFO)
logging.info(f"Using websockets library version: {websockets.__version__}")

# --- Gemini API 설정 ---
GEMINI_API_KEY = "" # 실제 API 키로 교체!
GEMINI_MODEL_NAME = "gemini-2.0-flash-live-001"
GEMINI_WS_URL_BASE = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
# -------------------------

# 웹 클라이언트와 Gemini 간 메시지 전달을 위한 큐
web_text_to_gemini_queue = asyncio.Queue() # 텍스트 메시지용
gemini_to_web_queue = asyncio.Queue() # 웹 클라이언트로 보낼 메시지 (텍스트 또는 오디오 정보)

connected_web_clients = set()
gemini_websocket_connection = None

# --- 카메라 설정 ---
picam2 = None
VIDEO_FPS = 1 # 초당 전송할 프레임 수 (조절 가능)
# ------------------

async def setup_camera():
    global picam2
    if picam2 is not None: # 이미 초기화 및 실행 중이면 반환
        try: # 간단한 상태 확인 시도
            picam2.capture_metadata()
            return True
        except Exception:
            logging.warning("Camera was initialized but seems unresponsive. Re-initializing.")
            try:
                picam2.close()
            except Exception:
                pass # 이미 닫혔거나 문제 있는 상태일 수 있음
            picam2 = None

    try:
        logging.info("Initializing camera...")
        picam2 = Picamera2()
        capture_config = picam2.create_still_configuration(main={"size": (640, 480)}) 
        picam2.configure(capture_config)
        picam2.start()
        logging.info("Camera setup successful and started.")
        return True
    except Exception as e:
        logging.error(f"Failed to setup or start camera: {e}")
        if picam2: # 부분적으로라도 초기화 되었다면 close 시도
            try:
                picam2.close()
            except Exception as ce_close:
                logging.error(f"Error closing camera during setup failure: {ce_close}")
        picam2 = None
        return False

async def stream_video_to_gemini():
    global gemini_websocket_connection, picam2
    
    # 앱 시작 시 카메라 설정 시도
    if not await setup_camera():
        logging.error("Initial camera setup failed. Video streaming will not start immediately.")

    while True:
        await asyncio.sleep(1.0 / VIDEO_FPS) 
        
        if picam2 is None or not picam2.started: # 카메라가 없거나 시작되지 않았다면 설정 시도
            logging.warning("Camera not running. Attempting to set up camera for video stream...")
            if not await setup_camera():
                logging.warning("Retrying camera setup in 5 seconds for video stream...")
                await asyncio.sleep(5) 
                continue # 다음 루프에서 다시 시도
        
        if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN and picam2 and picam2.started:
            try:
                buffer = io.BytesIO()
                picam2.capture_file(buffer, format='jpeg') # 기본 품질 사용
                buffer.seek(0)
                image_bytes = buffer.read()
                
                if not image_bytes:
                    logging.warning("Captured empty image, skipping frame.")
                    continue

                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                
                gemini_video_input = {
                    "realtimeInput": {
                        "video": {"data": image_base64, "mimeType": "image/jpeg"}
                    }
                }
                await gemini_websocket_connection.send(json.dumps(gemini_video_input))
                logging.debug(f"Sent video frame to Gemini ({len(image_bytes)} bytes).")

            except Exception as e:
                logging.error(f"Error capturing or sending video frame: {e}")
                if isinstance(e, RuntimeError) and ("Camera not running" in str(e) or "No data available" in str(e)):
                    logging.info("Camera seems to have stopped. Attempting to re-initialize camera...")
                    if picam2:
                        try: picam2.close()
                        except Exception: pass
                    picam2 = None # 재설정 강제
                    await asyncio.sleep(1) # 짧은 지연 후 재시도
                else:
                    await asyncio.sleep(2) # 다른 일반적인 오류의 경우 잠시 대기 후 재시도
        else:
            logging.debug("Gemini not connected or camera not ready. Skipping video frame.")
            await asyncio.sleep(1) # 대기

async def gemini_processor():
    global gemini_websocket_connection
    if GEMINI_API_KEY == "YOUR_API_KEY_HERE":
        logging.error("Gemini API Key is not set. Please update GEMINI_API_KEY in main.py.")
        await gemini_to_web_queue.put(json.dumps({"type": "status", "message": "Error: Gemini API Key not configured on the server."}))
        return

    uri_with_key = f"{GEMINI_WS_URL_BASE}?key={GEMINI_API_KEY}"
    
    while True: 
        try:
            async with websockets.connect(uri_with_key) as gemini_ws:
                gemini_websocket_connection = gemini_ws 
                logging.info("Successfully connected to Gemini Live API.")

                setup_message = {
                    "setup": {
                        "model": f"models/{GEMINI_MODEL_NAME}",
                        "generationConfig": {
                            "responseModalities": ["AUDIO"], # 오디오 응답 요청으로 변경
                        },
                        "outputAudioTranscription": {}, # 최상위 setup 객체 내로 이동
                        "systemInstruction": {
                            "parts": [{"text": "You are a friendly and helpful Raspberry Pi assistant."}]
                        }
                        # "speechConfig": { # 필요시 음성 설정 추가 (docs/gemini-live-api.md 참고)
                        #     "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Puck"}}
                        # }
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
                    await gemini_to_web_queue.put(json.dumps({"type": "status", "message": f"Error: {error_msg}"}))
                    gemini_websocket_connection = None 
                    await asyncio.sleep(5) 
                    continue 

                logging.info("Gemini session setup complete.")
                await gemini_to_web_queue.put(json.dumps({"type": "status", "message": "[Gemini session ready]"}))

                async def forward_text_to_gemini():
                    while True:
                        if not gemini_websocket_connection: break
                        try:
                            message_from_web = await web_text_to_gemini_queue.get()
                            if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
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
                                web_text_to_gemini_queue.put_nowait(message_from_web) 
                                break
                        except websockets.exceptions.ConnectionClosed:
                            logging.warning("Connection to Gemini closed (forward_text_to_gemini).")
                            if 'message_from_web' in locals(): web_text_to_gemini_queue.put_nowait(message_from_web) 
                            break
                        except Exception as e_fwd:
                            logging.error(f"Error in forward_text_to_gemini: {e_fwd}")
                        finally:
                             if 'message_from_web' in locals() and web_text_to_gemini_queue.empty() is False : 
                                web_text_to_gemini_queue.task_done()


                async def receive_from_gemini():
                    while True:
                        if not gemini_websocket_connection: break
                        try:
                            message_from_gemini_raw = await gemini_websocket_connection.recv()
                            logging.debug(f"Raw from Gemini: {message_from_gemini_raw[:200]}") # Debugging
                            message_data = json.loads(message_from_gemini_raw)
                            
                            message_for_web = None

                            if "serverContent" in message_data:
                                server_content = message_data["serverContent"]
                                
                                # 오디오 데이터 처리
                                if "modelTurn" in server_content and server_content["modelTurn"].get("parts"):
                                    for part in server_content["modelTurn"]["parts"]:
                                        if "inlineData" in part and part["inlineData"].get("mimeType", "").startswith("audio/pcm"):
                                            audio_base64 = part["inlineData"]["data"]
                                            logging.info(f"Received AUDIO data from Gemini (approx {len(audio_base64)*3/4} bytes of PCM).")
                                            message_for_web = {"type": "audio_data", "payload": audio_base64}
                                            # 오디오와 함께 트랜스크립션이 올 수도 있으므로, 계속 다른 part도 확인
                                
                                # 텍스트 트랜스크립션 처리 (outputAudioTranscription)
                                if "outputTranscription" in server_content and server_content["outputTranscription"].get("text"):
                                    transcription_text = server_content["outputTranscription"]["text"]
                                    logging.info(f"Received Output Transcription: {transcription_text}")
                                    # 오디오 데이터와 트랜스크립션을 별도 메시지로 보낼지, 합칠지 결정 필요.
                                    # 여기서는 별도 상태 메시지로 전송.
                                    if message_for_web is None: # 오디오 데이터가 없는 경우 (예: 텍스트 응답만)
                                         message_for_web = {"type": "status", "message": f"[Transcript]: {transcription_text}"}
                                    else: # 오디오 데이터가 이미 있다면, 트랜스크립션은 별도 메시지로.
                                        await gemini_to_web_queue.put(json.dumps({"type": "status", "message": f"[Transcript]: {transcription_text}"}))


                                # 텍스트 응답 (예: responseModalities가 TEXT일 때 또는 오류 메시지)
                                # modelTurn.parts에 text가 있는 경우도 고려 (audio와 함께 올 수 있음)
                                if "modelTurn" in server_content and server_content["modelTurn"].get("parts"):
                                    text_response_part = ""
                                    for part in server_content["modelTurn"]["parts"]:
                                        if "text" in part: # 오디오 외의 텍스트 파트 (거의 없을 것으로 예상되나 방어 코드)
                                            text_response_part += part["text"] + " "
                                    if text_response_part.strip() and message_for_web is None: # 오디오 데이터가 없고 텍스트만 있다면
                                        logging.info(f"Received TEXT response from Gemini: {text_response_part.strip()}")
                                        message_for_web = {"type": "status", "message": text_response_part.strip()}
                                    elif text_response_part.strip(): # 오디오도 있고 텍스트도 있다면 (거의 없을 상황)
                                        await gemini_to_web_queue.put(json.dumps({"type": "status", "message": text_response_part.strip()}))


                                if "interrupted" in server_content and server_content["interrupted"]:
                                    logging.info("Gemini: Interrupted by new input")
                                    if message_for_web is None: message_for_web = {"type": "status", "message": "[Gemini: Interrupted]"}
                                
                                if "turnComplete" in server_content and server_content["turnComplete"]:
                                    logging.info("Gemini: Turn complete.")
                                    # 턴 완료 메시지는 별도로 보내거나, 마지막 데이터에 포함시킬 수 있음
                                    # 여기서는 별도 상태 메시지로 전송하지 않음 (오디오 스트림의 끝으로 간주)

                            elif "toolCall" in message_data:
                                logging.info(f"Received Tool Call from Gemini: {message_data['toolCall']}")
                                message_for_web = {"type": "status", "message": f"[Gemini Tool Call (not yet handled)]"}
                            elif "goAway" in message_data:
                                logging.warning(f"Gemini server sent GoAway: {message_data['goAway']}")
                                message_for_web = {"type": "status", "message": "[Gemini session ending]"}
                                break 
                            else: # 기타 Gemini 메시지
                                logging.info(f"Received unhandled message structure from Gemini: {message_from_gemini_raw[:200]}...")
                                # message_for_web = {"type": "status", "message": "[Gemini: Unhandled message structure]"}


                            if message_for_web:
                                await gemini_to_web_queue.put(json.dumps(message_for_web))

                        except websockets.exceptions.ConnectionClosed:
                            logging.warning("Connection to Gemini closed (receive_from_gemini).")
                            break 
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
            gemini_websocket_connection = None 
            logging.info("Gemini processor attempting to reconnect or has finished a cycle.")
            await gemini_to_web_queue.put(json.dumps({"type": "status", "message": "[Error: Disconnected from Gemini. Attempting to reconnect...]"}),)
            await asyncio.sleep(5) 


async def rpi_websocket_handler(websocket, path=None):
    global gemini_websocket_connection
    logging.info(f"Web client connected: {websocket.remote_address}")
    connected_web_clients.add(websocket)
    try:
        async for message_from_web in websocket:
            if isinstance(message_from_web, str): 
                try:
                    data = json.loads(message_from_web)
                    if data.get("type") == "audio_stream_end":
                        logging.info(f"Received audio_stream_end signal from {websocket.remote_address}")
                        if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
                            end_signal_message = {"realtimeInput": {"audioStreamEnd": True}}
                            await gemini_websocket_connection.send(json.dumps(end_signal_message))
                            logging.info("Sent audioStreamEnd:true to Gemini.")
                        # continue # audio_stream_end는 턴을 종료시키므로, 추가 텍스트 입력이 없으면 여기서 끝.
                    else: # 기타 JSON (향후 확장용) 또는 알 수 없는 JSON
                        logging.info(f"Received JSON from web client {websocket.remote_address}: {message_from_web}")
                        # 일반 텍스트처럼 Gemini로 보낼지 여부 결정. 지금은 로깅만.
                except json.JSONDecodeError:
                    # JSON 파싱 실패 시 일반 텍스트 메시지로 간주
                    logging.info(f"Received TEXT from web client {websocket.remote_address}: {message_from_web}")
                    await web_text_to_gemini_queue.put(message_from_web)
                
            elif isinstance(message_from_web, bytes): 
                logging.info(f"Received AUDIO ({len(message_from_web)} bytes) from web client {websocket.remote_address}")
                if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
                    try:
                        audio_base64 = base64.b64encode(message_from_web).decode('utf-8')
                        gemini_realtime_input = {
                            "realtimeInput": {
                                "audio": {"data": audio_base64, "mimeType": "audio/pcm;rate=16000"}
                            }
                        }
                        await gemini_websocket_connection.send(json.dumps(gemini_realtime_input))
                        # logging.info("Sent audio chunk to Gemini.") # 너무 자주 로깅되므로 DEBUG 레벨로 변경 또는 주석 처리
                        logging.debug("Sent audio chunk to Gemini.")
                    except websockets.exceptions.ConnectionClosed:
                        logging.warning("Gemini connection closed. Cannot send audio.")
                    except Exception as e_audio_send:
                        logging.error(f"Error sending audio to Gemini: {e_audio_send}")
                else:
                    logging.warning("Gemini not connected. Cannot send audio.")
            else:
                logging.warning(f"Received unknown message type from {websocket.remote_address}")

    except websockets.exceptions.ConnectionClosedOK:
        logging.info(f"Web client {websocket.remote_address} disconnected normally.")
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"Web client {websocket.remote_address} connection closed with error: {e}")
    except Exception as e:
        logging.error(f"An error with web client {websocket.remote_address}: {e}")
    finally:
        logging.info(f"Web client connection handler for {websocket.remote_address} finished.")
        connected_web_clients.remove(websocket)


async def broadcast_gemini_responses():
    while True:
        message_to_broadcast_json = await gemini_to_web_queue.get()
        active_clients = list(connected_web_clients) 
        if active_clients:
            results = await asyncio.gather(
                *[client_ws.send(message_to_broadcast_json) for client_ws in active_clients], # JSON 문자열 그대로 전송
                return_exceptions=True
            )
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"Error sending to client {active_clients[i].remote_address}: {result}")
        gemini_to_web_queue.task_done()


async def start_main_server():
    server_host = "0.0.0.0"
    server_port = 8765
    logging.info(f"Starting RPi WebSocket server on ws://{server_host}:{server_port}")

    asyncio.create_task(gemini_processor())
    asyncio.create_task(broadcast_gemini_responses())
    asyncio.create_task(stream_video_to_gemini()) # 비디오 스트리밍 태스크 추가

    async with websockets.serve(rpi_websocket_handler, server_host, server_port):
        await asyncio.Future()  

if __name__ == "__main__":
    try:
        # 로깅 레벨을 DEBUG로 설정하여 더 자세한 정보 확인 (필요시)
        # logging.getLogger().setLevel(logging.DEBUG) 
        asyncio.run(start_main_server())
    except KeyboardInterrupt:
        logging.info("Main server shutting down.")
    except Exception as e:
        logging.error(f"Failed to start main server: {e}")