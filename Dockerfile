# RunPod PyTorch imajını kullan
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04 AS runtime

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    git wget aria2 ffmpeg libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
RUN pip install --no-cache-dir \
    runpod websocket-client huggingface_hub[hf_transfer] \
    sageattention accelerate diffusers transformers \
    sentencepiece protobuf spandrel spandrel_extra_arches

WORKDIR /

# ComfyUI kurulumu
RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd /ComfyUI && git checkout master && \
    pip install -r requirements.txt

# Custom Nodes kurulumu
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git && \
    git clone https://github.com/Fannovel16/ComfyUI-Frame-Interpolation.git

# Eklenti bağımlılıkları (Doğru dosya ismi: requirements-no-cupy.txt)
RUN cd /ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && pip install -r requirements.txt
RUN cd /ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation && pip install -r requirements-no-cupy.txt

# Model: RealESRGAN_x2plus (Hızlı 2x Upscale)
RUN mkdir -p /ComfyUI/models/upscale_models && \
    aria2c -x 16 -s 16 -k 1M --allow-overwrite=true \
    -d /ComfyUI/models/upscale_models -o RealESRGAN_x2plus.pth \
    "https://huggingface.co/dtarnow/UPscaler/resolve/main/RealESRGAN_x2plus.pth"

# Model: RIFE 4.7 (Interpolation) - Doğru Klasör: vfi_models/rife
RUN mkdir -p /ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/vfi_models/rife && \
    aria2c -x 16 -s 16 -k 1M --allow-overwrite=true \
    -d /ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/vfi_models/rife -o rife47.pth \
    "https://huggingface.co/jasonot/mycomfyui/resolve/main/rife47.pth"

# Model: Wan2.2 UNET (High & Low Noise) - Sadeleştirilmiş
RUN mkdir -p /ComfyUI/models/unet/Wan2.2 && \
    aria2c -x 16 -s 16 -k 1M --allow-overwrite=true -d /ComfyUI/models/unet/Wan2.2 -o wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors" && \
    aria2c -x 16 -s 16 -k 1M --allow-overwrite=true -d /ComfyUI/models/unet/Wan2.2 -o wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors"

# Model: Wan2.2 LoRAs - Sadeleştirilmiş
RUN aria2c -x 16 -s 16 -k 1M --allow-overwrite=true -d /ComfyUI/models/loras -o wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors" && \
    aria2c -x 16 -s 16 -k 1M --allow-overwrite=true -d /ComfyUI/models/loras -o wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors"

# Model: CLIP & VAE - Sadeleştirilmiş
RUN aria2c -x 16 -s 16 -k 1M --allow-overwrite=true -d /ComfyUI/models/clip -o umt5_xxl_fp8_e4m3fn_scaled.safetensors "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" && \
    aria2c -x 16 -s 16 -k 1M --allow-overwrite=true -d /ComfyUI/models/vae -o wan_2.1_vae.safetensors "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"

# Cache Buster (Dosyaların güncel halini zorla kopyalamak için)
ENV CACHE_BUSTER=2026-01-31_v5

# Çalışma dosyalarını kopyala
COPY handler.py /handler.py
COPY entrypoint.sh /entrypoint.sh
COPY video_wan2_2_14B_t2v.json /workflow.json

RUN chmod +x /entrypoint.sh

# Model cache için environment
ENV HF_HOME=/tmp/huggingface
ENV TRANSFORMERS_CACHE=/tmp/transformers

CMD ["/entrypoint.sh"]