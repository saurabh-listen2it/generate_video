#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Start ComfyUI in the background
echo "Starting ComfyUI in the background..."
# --lowvram ve --preview-method auto ekleyerek bellek kullanımını optimize ediyoruz
python /ComfyUI/main.py --listen --use-sage-attention --lowvram --preview-method auto > /tmp/comfyui.log 2>&1 &

# Wait for ComfyUI to be ready
echo "Waiting for ComfyUI to be ready (Max 10 minutes)..."
max_wait=600  # Modeller büyük olduğu için 10 dakikaya çıkardık
wait_count=0
while [ $wait_count -lt $max_wait ]; do
    if curl -s http://127.0.0.1:8188/ > /dev/null 2>&1; then
        echo "ComfyUI is ready!"
        break
    fi
    echo "Waiting for ComfyUI... ($wait_count/$max_wait)"
    # Log dosyasının son satırını göstererek ne olduğunu anlayalım
    tail -n 1 /tmp/comfyui.log || true
    sleep 5
    wait_count=$((wait_count + 5))
done

if [ $wait_count -ge $max_wait ]; then
    echo "Error: ComfyUI failed to start within $max_wait seconds"
    echo "--- Last ComfyUI Logs ---"
    cat /tmp/comfyui.log
    exit 1
fi

# Start the handler in the foreground
echo "Starting the handler..."
exec python -u handler.py
