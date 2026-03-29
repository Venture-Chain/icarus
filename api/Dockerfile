FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1

# Pre-configure timezone so no package triggers the interactive tzdata prompt.
RUN echo "Etc/UTC" > /etc/timezone \
    && ln -snf /usr/share/zoneinfo/Etc/UTC /etc/localtime \
    && apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN DEBIAN_FRONTEND=noninteractive pip install --no-cache-dir -r requirements.txt

# ibapi is not on PyPI. Install from official IBKR wheel.
# Download from: https://interactivebrokers.github.io/
RUN pip install --no-cache-dir ibapi 2>/dev/null \
    || echo "ibapi not available on PyPI, IB features disabled until manually installed"

# PyTorch CPU-only (slim, ~200MB instead of 2GB).
# Optional: falls back gracefully if the wheel index has no match for this platform.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu 2>/dev/null \
    || echo "torch CPU wheel not available for this platform, ML features require manual install"

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
