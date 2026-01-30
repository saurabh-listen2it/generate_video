#!/bin/bash

set -e

echo "=== Wan2.2 Serverless Başlatılıyor ==="

# ComfyUI log dosyası
LOG_FILE="/tmp/comfyui.log"

# ComfyUI'yi başlat
echo "ComfyUI başlatılıyor..."
python /ComfyUI/main.py \
    --listen 0.0.0.0 \
    --port 8188 \
    --use-sage-attention \
    --lowvram \
    --preview-method auto \
    > "$LOG_FILE" 2>&1 &

COMFY_PID=$!
echo "ComfyUI PID: $COMFY_PID"

# ComfyUI'nin hazır olmasını bekle
echo "ComfyUI hazır olması bekleniyor (max 10 dk)..."
MAX_WAIT=600
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
        echo "✅ ComfyUI hazır!"
        break
    fi
    
    # Her 10 saniyede bir log göster
    if [ $((WAIT_COUNT % 10)) -eq 0 ]; then
        echo "Bekleniyor... ($WAIT_COUNT/$MAX_WAIT sn)"
        if [ -f "$LOG_FILE" ]; then
            tail -n 3 "$LOG_FILE" | head -n 1 || true
        fi
    fi
    
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "❌ HATA: ComfyUI başlatılamadı (timeout)"
    echo "--- Son Loglar ---"
    tail -n 50 "$LOG_FILE" || true
    kill $COMFY_PID 2>/dev/null || true
    exit 1
fi

# Model dosyalarının varlığını kontrol et
echo "=== Model Dosyaları Kontrol Ediliyor ==="
MODELS_OK=true

if [ ! -f "/ComfyUI/models/unet/Wan2.2/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors" ]; then
    echo "❌ HIGH noise model eksik"
    MODELS_OK=false
fi

if [ ! -f "/ComfyUI/models/unet/Wan2.2/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors" ]; then
    echo "❌ LOW noise model eksik"
    MODELS_OK=false
fi

if [ ! -f "/ComfyUI/models/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors" ]; then
    echo "❌ HIGH noise LoRA eksik"
    MODELS_OK=false
fi

if [ ! -f "/ComfyUI/models/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors" ]; then
    echo "❌ LOW noise LoRA eksik"
    MODELS_OK=false
fi

if [ ! -f "/ComfyUI/models/clip/umt5_xxl_fp8_e4m3fn_scaled.safetensors" ]; then
    echo "❌ CLIP model eksik"
    MODELS_OK=false
fi

if [ ! -f "/ComfyUI/models/vae/wan_2.1_vae.safetensors" ]; then
    echo "❌ VAE model eksik"
    MODELS_OK=false
fi

if [ "$MODELS_OK" = false ]; then
    echo "❌ Kritik model dosyaları eksik!"
    exit 1
fi

echo "✅ Tüm model dosyaları mevcut"

# Handler'ı başlat
echo "=== Handler Başlatılıyor ==="
exec python -u /handler.py
