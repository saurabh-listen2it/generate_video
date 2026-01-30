# RunPod PyTorch imajını kullan
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04 AS runtime

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    git \
    wget \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
RUN pip install --no-cache-dir \
    runpod \
    websocket-client \
    huggingface_hub[hf_transfer] \
    sageattention \
    accelerate \
    diffusers \
    transformers \
    sentencepiece \
    protobuf

WORKDIR /

# ComfyUI'yi kur (Wan2.2 native support için doğru sürüm)
RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd /ComfyUI && \
    git checkout master && \
    pip install -r requirements.txt

# Gerekli custom nodes (minimal set)
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git

# VideoHelperSuite bağımlılıkları
RUN cd /ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && \
    pip install -r requirements.txt

# Model dosyalarını indir
# Diffusion models (Wan2.2 T2V)
RUN mkdir -p /ComfyUI/models/unet/Wan2.2 && \
    wget -q --show-progress \
    https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors \
    -O /ComfyUI/models/unet/Wan2.2/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors && \
    wget -q --show-progress \
    https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors \
    -O /ComfyUI/models/unet/Wan2.2/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors

# LoRA dosyaları
RUN wget -q --show-progress \
    https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors \
    -O /ComfyUI/models/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors && \
    wget -q --show-progress \
    https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors \
    -O /ComfyUI/models/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors

# Text encoder (CLIP)
RUN wget -q --show-progress \
    https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
    -O /ComfyUI/models/clip/umt5_xxl_fp8_e4m3fn_scaled.safetensors

# VAE (Wan2.1 VAE - Workflow bu ismi bekliyor)
RUN wget -q --show-progress \
    https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors \
    -O /ComfyUI/models/vae/wan_2.1_vae.safetensors

# Çalışma dosyalarını kopyala
COPY handler.py /handler.py
COPY entrypoint.sh /entrypoint.sh
COPY video_wan2_2_14B_t2v.json /workflow.json

RUN chmod +x /entrypoint.sh

# Model cache için environment
ENV HF_HOME=/tmp/huggingface
ENV TRANSFORMERS_CACHE=/tmp/transformers

CMD ["/entrypoint.sh"]
