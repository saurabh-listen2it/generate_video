import runpod
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.error
import urllib.parse
import time
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())

def to_nearest_multiple_of_16(value):
    """Değeri 16'nın katına yuvarla, minimum 16"""
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height değeri geçersiz: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted

def queue_prompt(prompt):
    """Prompt'u ComfyUI'ye gönder"""
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Prompt gönderiliyor: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    
    logger.info(f"JSON boyutu: {len(data)} bytes")
    
    req = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json'
    })
    
    try:
        response = urllib.request.urlopen(req, timeout=300)
        return json.loads(response.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        logger.error(f"ComfyUI Hatası: {e.code} - {e.reason}")
        logger.error(f"Hata detayı: {error_body}")
        raise Exception(f"ComfyUI Hatası {e.code}: {error_body}")
    except Exception as e:
        logger.error(f"Prompt gönderme hatası: {e}")
        raise

def get_history(prompt_id):
    """Prompt sonuçlarını al"""
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Sonuçlar alınıyor: {url}")
    
    max_retries = 30
    for i in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                history = json.loads(response.read())
                if prompt_id in history:
                    return history[prompt_id]
        except Exception as e:
            logger.warning(f"History alma denemesi {i+1}/{max_retries}: {e}")
        time.sleep(2)
    
    raise Exception("History alınamadı (timeout)")

def get_video_file(node_output):
    """Video dosyasını bul ve oku"""
    logger.info(f"get_video_file çağrıldı, node_output keys: {list(node_output.keys())}")

    # SaveVideo node output formatını kontrol et (VideoHelperSuite 'images' key kullanıyor)
    for key in ['images', 'gifs', 'videos', 'files']:
        if key in node_output:
            logger.info(f"'{key}' key'i bulundu, içerik: {node_output[key]}")
            for item in node_output[key]:
                if isinstance(item, dict):
                    filename = item.get('filename', '')
                    subfolder = item.get('subfolder', '')
                    type_ = item.get('type', '')

                    logger.info(f"Dict item - filename: {filename}, subfolder: {subfolder}, type: {type_}")

                    # Sadece video/output türlerini kontrol et
                    if type_ not in ['output', 'temp'] and key != 'gifs':
                        logger.info(f"Tip eşleşmedi, atlanıyor")
                        continue

                    # Video dosyasının tam yolunu oluştur
                    if subfolder:
                        video_path = f"/ComfyUI/output/{subfolder}/{filename}"
                    else:
                        video_path = f"/ComfyUI/output/{filename}"

                    logger.info(f"Video aranıyor: {video_path}")
                    logger.info(f"Dosya var mı: {os.path.exists(video_path)}")

                    if os.path.exists(video_path):
                        logger.info(f"✅ Video bulundu: {video_path}")
                        with open(video_path, 'rb') as f:
                            video_data = base64.b64encode(f.read()).decode('utf-8')
                            logger.info(f"Video boyutu: {len(video_data)} bytes (base64)")
                            return video_data
                    else:
                        logger.warning(f"❌ Video dosyası bulunamadı: {video_path}")
                        # /ComfyUI/output/ altındaki tüm dosyaları listele
                        try:
                            output_files = os.listdir('/ComfyUI/output/')
                            logger.info(f"Output klasöründeki dosyalar: {output_files}")
                            # Subfolder'ları da kontrol et
                            for item_name in output_files:
                                item_path = f"/ComfyUI/output/{item_name}"
                                if os.path.isdir(item_path):
                                    subfiles = os.listdir(item_path)
                                    logger.info(f"  {item_name}/ içindekiler: {subfiles}")
                        except Exception as e:
                            logger.error(f"Output klasörü okunamadı: {e}")

                elif isinstance(item, str):
                    # String formatı için
                    video_path = f"/ComfyUI/output/{item}"
                    logger.info(f"String item, video aranıyor: {video_path}")
                    if os.path.exists(video_path):
                        logger.info(f"✅ Video bulundu (string): {video_path}")
                        with open(video_path, 'rb') as f:
                            return base64.b64encode(f.read()).decode('utf-8')

    logger.error("❌ Hiçbir key'de video bulunamadı")
    return None

def execute_workflow(prompt):
    """Workflow'u çalıştır ve sonuçları al"""
    # Prompt'u gönder
    result = queue_prompt(prompt)
    prompt_id = result.get('prompt_id')
    
    if not prompt_id:
        raise Exception("Prompt ID alınamadı")
    
    logger.info(f"Prompt ID: {prompt_id}")
    
    # WebSocket ile execution durumunu takip et
    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    ws = websocket.WebSocket()
    
    try:
        # Timeout'u 10 dakikaya çıkarıyoruz (Model yükleme ve ilk adım için)
        ws.connect(ws_url, timeout=600)
        logger.info("WebSocket bağlantısı kuruldu, execution takibi başlıyor...")
        
        while True:
            try:
                msg = ws.recv()
                if not msg:
                    break
            except websocket.WebSocketTimeoutException:
                logger.warning("WebSocket recv timeout - hala bekleniyor...")
                continue
                
            if isinstance(msg, str):
                data = json.loads(msg)
                msg_type = data.get('type', '')
                
                if msg_type == 'status':
                    status = data.get('data', {}).get('status', {})
                    queue_remaining = status.get('exec_info', {}).get('queue_remaining', 0)
                    if queue_remaining > 0:
                        logger.info(f"Sırada bekleyen iş var: {queue_remaining}")

                elif msg_type == 'executing':
                    exec_data = data.get('data', {})
                    node = exec_data.get('node')
                    current_id = exec_data.get('prompt_id')
                    
                    if current_id == prompt_id:
                        if node is None:
                            logger.info("Workflow tamamlandı")
                            break
                        else:
                            logger.info(f"Şu an çalışan node: {node}")
                
                elif msg_type == 'progress':
                    progress_data = data.get('data', {})
                    current = progress_data.get('value')
                    total = progress_data.get('max')
                    logger.info(f"İlerleme: {current}/{total}")
                        
                elif msg_type == 'execution_error':
                    error_data = data.get('data', {})
                    logger.error(f"Execution hatası: {error_data}")
                    raise Exception(f"Workflow hatası: {error_data}")
    except Exception as e:
        logger.error(f"WebSocket döngüsünde hata: {e}")
        raise
    finally:
        ws.close()
    
    # Sonuçları al
    history = get_history(prompt_id)
    outputs = history.get('outputs', {})

    logger.info(f"Output node'ları: {list(outputs.keys())}")

    # DEBUG: Tam output formatını göster
    if '80' in outputs:
        logger.info(f"Node 80 output içeriği: {json.dumps(outputs['80'], indent=2)}")
    
    # Video dosyasını bul (node 80: SaveVideo)
    if '80' in outputs:
        video_data = get_video_file(outputs['80'])
        if video_data:
            return {"video": video_data}
    
    # Tüm nodeları kontrol et
    for node_id, node_output in outputs.items():
        video_data = get_video_file(node_output)
        if video_data:
            logger.info(f"Video node {node_id}'den alındı")
            return {"video": video_data}
    
    raise Exception("Video output bulunamadı")

def handler(job):
    """RunPod handler fonksiyonu"""
    job_input = job.get("input", {})
    
    logger.info(f"Job input alındı: {job_input}")
    
    # Workflow'u yükle
    workflow_path = "/workflow.json"
    with open(workflow_path, 'r') as f:
        prompt = json.load(f)
    
    logger.info(f"Workflow yüklendi: {len(prompt)} node")
    
    # Parametreleri al
    positive_prompt = job_input.get("prompt", "")
    negative_prompt = job_input.get("negative_prompt", 
        "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走，裸露，NSFW")
    
    width = to_nearest_multiple_of_16(job_input.get("width", 640))
    height = to_nearest_multiple_of_16(job_input.get("height", 640))
    length = job_input.get("length", 81)
    seed = job_input.get("seed", 42)
    cfg = job_input.get("cfg", 1.0)
    steps = job_input.get("steps", 4)
    
    logger.info(f"Parametreler: {width}x{height}, {length} frames, seed={seed}, cfg={cfg}, steps={steps}")
    
    # Workflow'u güncelle
    # Node 89: Positive prompt (CLIPTextEncode)
    if "89" in prompt:
        prompt["89"]["inputs"]["text"] = positive_prompt
    
    # Node 72: Negative prompt (CLIPTextEncode)
    if "72" in prompt:
        prompt["72"]["inputs"]["text"] = negative_prompt
    
    # Node 74: EmptyHunyuanLatentVideo (resolution ve frames)
    if "74" in prompt:
        prompt["74"]["inputs"]["width"] = width
        prompt["74"]["inputs"]["height"] = height
        prompt["74"]["inputs"]["length"] = length
    
    # Node 81: HIGH noise sampler (KSamplerAdvanced)
    if "81" in prompt:
        prompt["81"]["inputs"]["noise_seed"] = seed
        prompt["81"]["inputs"]["cfg"] = cfg
        prompt["81"]["inputs"]["steps"] = steps
        prompt["81"]["inputs"]["end_at_step"] = steps // 2
    
    # Node 78: LOW noise sampler (KSamplerAdvanced)
    if "78" in prompt:
        prompt["78"]["inputs"]["noise_seed"] = 0  # LOW sampler seed=0
        prompt["78"]["inputs"]["cfg"] = cfg
        prompt["78"]["inputs"]["steps"] = steps
        prompt["78"]["inputs"]["start_at_step"] = steps // 2
        prompt["78"]["inputs"]["end_at_step"] = steps
    
    # Node 88: CreateVideo (FPS ayarı)
    if "88" in prompt:
        fps = job_input.get("fps", 16)
        multiplier = job_input.get("multiplier", 2)
        
        # RIFE multiplier ayarı
        if "90" in prompt:
            prompt["90"]["inputs"]["multiplier"] = multiplier
            logger.info(f"DEBUG: RIFE (Node 90) multiplier set to {multiplier}")
        
        # Upscale ayarı (Model 4x büyütür, biz buradan çarpanla ayarlarız)
        if "93" in prompt:
            # Kullanıcı 2x istiyorsa, model 4x büyüttüğü için çarpanı 0.5 yaparız (4 * 0.5 = 2)
            user_upscale = job_input.get("upscale", 2)
            final_scale_multiplier = user_upscale / 4.0
            prompt["93"]["inputs"]["upscale_by"] = final_scale_multiplier
            logger.info(f"DEBUG: Final Scale Multiplier (Node 93) set to {final_scale_multiplier} (for {user_upscale}x total)")
        
        # Final FPS hesaplama (Orijinal FPS * Çarpan)
        final_fps = fps * multiplier
        prompt["88"]["inputs"]["fps"] = final_fps
        logger.info(f"DEBUG: Final Video FPS: {final_fps} (Base: {fps} x Multiplier: {multiplier})")
    
    logger.info(">>> Workflow update completed. Injecting into ComfyUI... <<<")
    
    try:
        # Workflow'u çalıştır
        logger.info(">>> Execution started! Tracking progress via WebSocket... <<<")
        result = execute_workflow(prompt)
        logger.info(">>> Video generation and post-processing successful! <<<")
        return result
        
    except Exception as e:
        logger.error(f"Workflow hatası: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
