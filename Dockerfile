#Base Image
FROM python:3.11-slim
#EnvironmentVariables
ENV PYTHONDONTWRITEBYTECODE = 1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860
#System Dependencies: OpenCV libs + Redis + buildtools
RUN apt-get update && apt-get install -y --no-install-recommends \
    #inlcudes some C/C++ tools
    build-essential \
    # ye kuch Linux system libraries hain needed for Opencv
    libgl1 \
    libglib2.00 \
    libsm6 \
    libxext6 \
    libxrender1 \
    #Install redis -server
    redis-server \
    #tool h jo URLs requests aur transferring data
    curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUn pip install --upgrade pip && \
    pip install torch==2.12.1 torchvision==0.27.1 \
        --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements. txt
# App code
COPY . .

# Static Files
RUN python manage.py collectstatic --noinput

# Non - root user (HF Spaces requirement)
RUN useradd -m -u 1000 user && \
    chown -R user:user /app
USER user

EXPOSE 7860

CMD["bash","start.sh"]