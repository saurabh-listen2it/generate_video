# RunPod'un resmi ve stabil PyTorch imajını kullanıyoruz
FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04 AS runtime

# Sistem bağımlılıklarını kur
RUN apt-get update && apt-get install -y \
    git \
    wget \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install -U "huggingface_hub[hf_transfer]"
RUN pip install runpod websocket-client

# Kritik kütüphaneleri build aşamasında kuruyoruz
RUN pip install sageattention accelerate diffusers transformers sentencepiece protobuf

WORKDIR /

# ComfyUI kurulumu
RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd /ComfyUI && \
    pip install -r requirements.txt

# Custom Nodes kurulumu
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    git clone https://github.com/city96/ComfyUI-GGUF && \
    git clone https://github.com/kijai/ComfyUI-KJNodes && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite && \
    git clone https://github.com/kael558/ComfyUI-GGUF-FantasyTalking && \
    git clone https://github.com/orssorbit/ComfyUI-wanBlockswap && \
    git clone https://github.com/kijai/ComfyUI-WanVideoWrapper && \
    git clone https://github.com/eddyhhlure1Eddy/IntelligentVRAMNode && \
    git clone https://github.com/eddyhhlure1Eddy/auto_wan2.2animate_freamtowindow_server && \
    git clone https://github.com/eddyhhlure1Eddy/ComfyUI-AdaptiveWindowSize

# Custom node gereksinimlerini kur
RUN cd /ComfyUI/custom_nodes/ComfyUI-Manager && pip install -r requirements.txt && \
    cd /ComfyUI/custom_nodes/ComfyUI-GGUF && pip install -r requirements.txt && \
    cd /ComfyUI/custom_nodes/ComfyUI-KJNodes && pip install -r requirements.txt && \
    cd /ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && pip install -r requirements.txt && \
    cd /ComfyUI/custom_nodes/ComfyUI-WanVideoWrapper && pip install -r requirements.txt

# Wan2.2 Native ComfyUI Models (Tested and Working)
# Create Wan2.2 subdirectory for diffusion models
RUN mkdir -p /ComfyUI/models/unet/Wan2.2

# Diffusion models (14B fp8 scaled)
RUN wget -q https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors -O /ComfyUI/models/unet/Wan2.2/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors
RUN wget -q https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors -O /ComfyUI/models/unet/Wan2.2/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors

# LoRAs (4-step optimization)
RUN wget -q https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors -O /ComfyUI/models/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors
RUN wget -q https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors -O /ComfyUI/models/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors

# Text encoder (CLIP)
RUN wget -q https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors -O /ComfyUI/models/clip/umt5_xxl_fp8_e4m3fn_scaled.safetensors

# VAE
RUN wget -q https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors -O /ComfyUI/models/vae/wan_2.1_vae.safetensors

COPY . .
COPY extra_model_paths.yaml /ComfyUI/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
