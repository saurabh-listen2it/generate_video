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

# SAGE ATTENTION ve diğer kritik kütüphaneleri build aşamasında kuruyoruz
# Bu sayede runtime'da vakit kaybetmiyoruz
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

# Custom node gereksinimlerini build'de kuruyoruz
RUN cd /ComfyUI/custom_nodes/ComfyUI-Manager && pip install -r requirements.txt && \
    cd /ComfyUI/custom_nodes/ComfyUI-GGUF && pip install -r requirements.txt && \
    cd /ComfyUI/custom_nodes/ComfyUI-KJNodes && pip install -r requirements.txt && \
    cd /ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && pip install -r requirements.txt && \
    cd /ComfyUI/custom_nodes/ComfyUI-WanVideoWrapper && pip install -r requirements.txt

# Wan2.2 T2V Modelleri (huggingface-cli ile güvenli indirme)
RUN huggingface-cli download Kijai/WanVideo_comfy_fp8_scaled T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors --local-dir /ComfyUI/models/diffusion_models --local-dir-use-symlinks False
RUN huggingface-cli download Kijai/WanVideo_comfy_fp8_scaled T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors --local-dir /ComfyUI/models/diffusion_models --local-dir-use-symlinks False

# Diğer modeller (huggingface-cli ile)
RUN huggingface-cli download Comfy-Org/Wan_2.1_ComfyUI_repackaged split_files/clip_vision/clip_vision_h.safetensors --local-dir /ComfyUI/models/clip_vision --local-dir-use-symlinks False
RUN huggingface-cli download Kijai/WanVideo_comfy umt5-xxl-enc-bf16.safetensors --local-dir /ComfyUI/models/text_encoders --local-dir-use-symlinks False
RUN huggingface-cli download Kijai/WanVideo_comfy Wan2_1_VAE_bf16.safetensors --local-dir /ComfyUI/models/vae --local-dir-use-symlinks False

# Dosyaları doğru yerlere taşı (HuggingFace klasör yapısını düzeltmek için)
# T2V Modelleri T2V klasöründen ana dizine
RUN mv /ComfyUI/models/diffusion_models/T2V/* /ComfyUI/models/diffusion_models/ && rmdir /ComfyUI/models/diffusion_models/T2V
# Clip Vision split_files klasöründen ana dizine
RUN mv /ComfyUI/models/clip_vision/split_files/clip_vision/* /ComfyUI/models/clip_vision/ && rm -rf /ComfyUI/models/clip_vision/split_files

COPY . .
COPY extra_model_paths.yaml /ComfyUI/extra_model_paths.yaml
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]