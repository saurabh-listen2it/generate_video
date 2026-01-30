import runpod
from runpod.serverless.utils import rp_upload
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import binascii # Base64 에러 처리를 위해 import
import subprocess
import time
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())
def to_nearest_multiple_of_16(value):
    """주어진 값을 가장 가까운 16의 배수로 보정, 최소 16 보장"""
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height 값이 숫자가 아닙니다: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted
def process_input(input_data, temp_dir, output_filename, input_type):
    """입력 데이터를 처리하여 파일 경로를 반환하는 함수"""
    if input_type == "path":
        # 경로인 경우 그대로 반환
        logger.info(f"📁 경로 입력 처리: {input_data}")
        return input_data
    elif input_type == "url":
        # URL인 경우 다운로드
        logger.info(f"🌐 URL 입력 처리: {input_data}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        return download_file_from_url(input_data, file_path)
    elif input_type == "base64":
        # Base64인 경우 디코딩하여 저장
        logger.info(f"🔢 Base64 입력 처리")
        return save_base64_to_file(input_data, temp_dir, output_filename)
    else:
        raise Exception(f"지원하지 않는 입력 타입: {input_type}")

        
def download_file_from_url(url, output_path):
    """URL에서 파일을 다운로드하는 함수"""
    try:
        # wget을 사용하여 파일 다운로드
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ URL에서 파일을 성공적으로 다운로드했습니다: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget 다운로드 실패: {result.stderr}")
            raise Exception(f"URL 다운로드 실패: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 다운로드 시간 초과")
        raise Exception("다운로드 시간 초과")
    except Exception as e:
        logger.error(f"❌ 다운로드 중 오류 발생: {e}")
        raise Exception(f"다운로드 중 오류 발생: {e}")


def save_base64_to_file(base64_data, temp_dir, output_filename):
    """Base64 데이터를 파일로 저장하는 함수"""
    try:
        # Base64 문자열 디코딩
        decoded_data = base64.b64decode(base64_data)
        
        # 디렉토리가 존재하지 않으면 생성
        os.makedirs(temp_dir, exist_ok=True)
        
        # 파일로 저장
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        logger.info(f"✅ Base64 입력을 '{file_path}' 파일로 저장했습니다.")
        return file_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ Base64 디코딩 실패: {e}")
        raise Exception(f"Base64 디코딩 실패: {e}")
    
def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')

    # Debug: Log the full prompt JSON
    logger.info(f"📤 Sending prompt JSON (first 500 chars): {json.dumps(p, indent=2)[:500]}...")

    req = urllib.request.Request(url, data=data)
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        logger.error(f"❌ ComfyUI Error: {e.code} - {e.reason}")
        logger.error(f"❌ Error Body: {error_body}")
        logger.error(f"❌ Prompt that failed (keys): {list(prompt.keys())}")
        raise e

def get_image(filename, subfolder, folder_type):
    url = f"http://{server_address}:8188/view"
    logger.info(f"Getting image from: {url}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{url}?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    logger.info(f"📋 History output nodes: {list(history['outputs'].keys())}")
    logger.info(f"📋 Full history structure: {json.dumps({k: list(v.keys()) for k, v in history['outputs'].items()}, indent=2)}")

    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        logger.info(f"🔍 Node {node_id} output keys: {list(node_output.keys())}")
        logger.info(f"🔍 Node {node_id} full output (first 500 chars): {str(node_output)[:500]}")
        videos_output = []

        # Try multiple possible output formats
        # SaveVideo (Native ComfyUI) may use 'videos', 'filenames', or other keys
        video_keys = ['gifs', 'videos', 'filenames', 'results']

        for key in video_keys:
            if key in node_output:
                logger.info(f"✅ Node {node_id} has '{key}' key with {len(node_output[key])} items")
                for video_item in node_output[key]:
                    # Handle different formats
                    if isinstance(video_item, dict):
                        video_path = video_item.get('fullpath') or video_item.get('filename') or video_item.get('path')
                    elif isinstance(video_item, str):
                        video_path = video_item
                    else:
                        logger.warning(f"⚠️  Unknown video item type: {type(video_item)}")
                        continue

                    if video_path:
                        logger.info(f"✅ Found video at: {video_path}")
                        try:
                            with open(video_path, 'rb') as f:
                                video_data = base64.b64encode(f.read()).decode('utf-8')
                            videos_output.append(video_data)
                            logger.info(f"✅ Successfully encoded video (size: {len(video_data)} chars)")
                        except Exception as e:
                            logger.error(f"❌ Failed to read video file {video_path}: {e}")
                break  # Found videos, stop looking

        if not videos_output:
            logger.warning(f"⚠️  Node {node_id} has no recognizable video output!")

        output_videos[node_id] = videos_output

    return output_videos

def load_workflow(workflow_path):
    with open(workflow_path, 'r') as file:
        return json.load(file)

def handler(job):
    job_input = job.get("input", {})

    logger.info(f"Received job input: {job_input}")
    task_id = f"task_{uuid.uuid4()}"

    # Sadece Text-to-Video (T2V) destekleniyor
    is_t2v = True
    logger.info("Sadece Text-to-Video modu aktif. Görsel girişleri yoksayılıyor.")

    # 워크플로우 파일 선택 (Native ComfyUI workflow)
    workflow_file = "/wan22_t2v_working.json"

    logger.info("Using Native ComfyUI T2V workflow (tested and working)")
    
    prompt = load_workflow(workflow_file)
    
    length = job_input.get("length", 81)
    steps = job_input.get("steps", 10)
    seed = job_input.get("seed", 42)
    cfg = job_input.get("cfg", 2.0)

    # Text Encode (Native ComfyUI nodes)
    # Node 89: Positive prompt (CLIPTextEncode)
    # Node 72: Negative prompt (CLIPTextEncode)
    prompt["89"]["inputs"]["text"] = job_input["prompt"]
    prompt["72"]["inputs"]["text"] = job_input.get("negative_prompt", "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走，裸露，NSFW")
    
    # KSampler settings (Native ComfyUI)
    # Node 81: HIGH noise sampler (steps 0-2)
    # Node 78: LOW noise sampler (steps 2-4)
    total_steps = job_input.get("steps", 4)  # Default 4 steps

    if "81" in prompt:
        prompt["81"]["inputs"]["noise_seed"] = seed
        prompt["81"]["inputs"]["cfg"] = cfg
        prompt["81"]["inputs"]["steps"] = total_steps
        prompt["81"]["inputs"]["end_at_step"] = total_steps // 2  # First half

    if "78" in prompt:
        prompt["78"]["inputs"]["noise_seed"] = 0  # LOW sampler uses seed 0
        prompt["78"]["inputs"]["cfg"] = cfg
        prompt["78"]["inputs"]["steps"] = total_steps
        prompt["78"]["inputs"]["start_at_step"] = total_steps // 2  # Second half
        prompt["78"]["inputs"]["end_at_step"] = total_steps

    # Resolution and Frame Count (Node 74: EmptyHunyuanLatentVideo)
    original_width = job_input.get("width", 640)
    original_height = job_input.get("height", 640)
    adjusted_width = to_nearest_multiple_of_16(original_width)
    adjusted_height = to_nearest_multiple_of_16(original_height)

    if "74" in prompt:
        prompt["74"]["inputs"]["width"] = adjusted_width
        prompt["74"]["inputs"]["height"] = adjusted_height
        prompt["74"]["inputs"]["length"] = length

    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    logger.info(f"Connecting to WebSocket: {ws_url}")
    
    # 먼저 HTTP 연결이 가능한지 확인
    http_url = f"http://{server_address}:8188/"
    logger.info(f"Checking HTTP connection to: {http_url}")
    
    # HTTP 연결 확인 (최대 1분)
    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            import urllib.request
            response = urllib.request.urlopen(http_url, timeout=5)
            logger.info(f"HTTP 연결 성공 (시도 {http_attempt+1})")
            break
        except Exception as e:
            logger.warning(f"HTTP 연결 실패 (시도 {http_attempt+1}/{max_http_attempts}): {e}")
            if http_attempt == max_http_attempts - 1:
                raise Exception("ComfyUI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
            time.sleep(1)
    
    ws = websocket.WebSocket()
    # 웹소켓 연결 시도 (최대 3분)
    max_attempts = int(180/5)  # 3분 (1초에 한 번씩 시도)
    for attempt in range(max_attempts):
        import time
        try:
            ws.connect(ws_url)
            logger.info(f"웹소켓 연결 성공 (시도 {attempt+1})")
            break
        except Exception as e:
            logger.warning(f"웹소켓 연결 실패 (시도 {attempt+1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise Exception("웹소켓 연결 시간 초과 (3분)")
            time.sleep(5)
    videos = get_videos(ws, prompt)
    ws.close()

    logger.info(f"📦 Total output nodes: {len(videos)}")
    for node_id, video_list in videos.items():
        logger.info(f"  - Node {node_id}: {len(video_list)} videos")

    # 이미지가 없는 경우 처리
    for node_id in videos:
        if videos[node_id]:
            logger.info(f"✅ Returning video from node {node_id}")
            return {"video": videos[node_id][0]}

    logger.error("❌ No videos found in any output node!")
    return {"error": "비디오를를 찾을 수 없습니다.", "debug_nodes": list(videos.keys())}

runpod.serverless.start({"handler": handler})